"""Agent orchestrator (11-23, user: "a real orchestrator"): one dispatcher for every background agent the engine
runs besides the appliers. The supervisor is its only writer: tick() runs on the supervisor's 15 s loop.

    agents (REGISTRY)       what can run: a CLI command (child process) or an in-process function, with a timeout,
                            retries, a daily budget, and the ladder level it needs (0 = the supervisor's own work)
    tasks (state.json)      one unit of work for one agent: queued -> leased -> done | failed (dead letter after
                            max_attempts, retried with exponential backoff before that); deduped by key while open
    sources                 periodic agents (every N s, or once a day after an hour) and Shadow's plan()
                            (engine/agents.py: retry a parked job, requeue a lost batch)

A tick: reap finished / overdue children -> schedule due periodic agents -> pull Shadow's plan -> dispatch queued
tasks while fewer than MAX_PROCS children run. A task whose agent is locked by the ladder, paused, over budget or
blocked by the KILL switch waits as "held" with the reason; nothing above Shadow's level ever runs. Every transition
is audited (kind "supervisor", action "orch_*"). A supervisor restart finds leases with no child: they are requeued
as lost (one attempt spent). O(tasks) per tick; finished tasks are pruned after KEEP_S.

    python -m engine orch [status]           agents, open tasks, the last finished ones
    python -m engine orch run <agent>        queue one run now (the supervisor dispatches it on its next tick)
    python -m engine orch pause|resume <agent>
"""
import json, os, subprocess, sys, time

from engine.config import WORKSPACE

DIR = os.path.join(WORKSPACE, "orchestrator")
STATE = os.path.join(DIR, "state.json")
LOGS = os.path.join(DIR, "logs")
MAX_PROCS = int(os.environ.get("REGEN_ORCH_PROCS", "2"))
KEEP_S = 3 * 86400
DAILY_HOUR = int(os.environ.get("REGEN_DAILY_HOUR", "7"))
OUTREACH_PER_DAY = int(os.environ.get("REGEN_OUTREACH_PER_DAY", "20"))

# kind "proc": `python -m engine <argv>` as the engine user; kind "fn": a function name in FNS, run inline (fast work).
# every: seconds between runs; at_hour: once a day after this local hour; neither: only on demand or from a plan.
# needs: ladder level (0 = supervisor-owned); imap: only when a Gmail app password is configured.
REGISTRY = {
    "hn":             {"kind": "proc", "argv": ["hn", "2"], "at_hour": DAILY_HOUR, "timeout": 1800, "budget": 2,
                       "why": "HN 'Who is hiring' boards + contacts"},
    "outreach":       {"kind": "proc", "argv": ["outreach", "7"], "at_hour": DAILY_HOUR, "after": "hn", "timeout": 1800,
                       "budget": 2, "why": "notes for the week's tier1 / sponsor / startup submissions (nothing sent)"},
    "outreach_gmail": {"kind": "proc", "argv": ["outreach", "hn", str(OUTREACH_PER_DAY), "--gmail", "--new"],
                       "at_hour": DAILY_HOUR, "after": "outreach", "imap": True, "timeout": 1800, "budget": 1,
                       "why": "Gmail DRAFTS for new HN contacts (never sent; the user reviews Drafts)"},
    "learn":          {"kind": "proc", "argv": ["learn"], "every": 6 * 3600, "timeout": 600, "budget": 6,
                       "why": "response rates by lane and ATS -> learnings.md"},
    "report_rate":    {"kind": "proc", "argv": ["report", "rate"], "every": 12 * 3600, "timeout": 600, "budget": 3,
                       "why": "interviews and OAs per 100 verified applications"},
    "boards_recheck": {"kind": "proc", "argv": ["boards", "recheck"], "at_hour": 3, "timeout": 3600, "budget": 1,
                       "why": "retry boards marked dead"},
    "shadow_retry":   {"kind": "fn", "fn": "shadow_retry", "needs": 2, "timeout": 120, "budget": 200, "attempts": 2,
                       "why": "Shadow retries a parked job it can answer in full (plan action 'retry')"},
    "requeue_batch":  {"kind": "fn", "fn": "requeue_batch", "needs": 2, "timeout": 120, "budget": 100, "attempts": 2,
                       "why": "a batch lost with its container goes back to the inbox (plan action 'requeue')"},
}
PLAN_AGENT = {"retry": "shadow_retry", "requeue": "requeue_batch"}  # plan action -> agent (scale stays the governor's)
OPEN = ("queued", "leased", "held")
PLAN_COOLDOWN = 30 * 60  # a plan action that ran is not queued again for 30 min (the runner needs time to retry it)
_PROCS = {}  # task id -> (Popen, log file): children of THIS supervisor process


def _now():
    return time.time()


def load(path=None):
    try:
        s = json.load(open(path or STATE, encoding="utf-8"))
    except (OSError, ValueError):
        s = {}
    s.setdefault("tasks", {})
    s.setdefault("agents", {})
    return s


def save(s, path=None):
    path = path or STATE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, default=str)
    os.replace(tmp, path)  # atomic: the api / MCP readers never see half a file
    _engine_owned(os.path.dirname(path), path)


def _engine_owned(*paths):
    """The supervisor runs as root; the api / CLI (uid 10001) must still drop requests and read logs here."""
    if os.name == "nt" or os.getuid() != 0:
        return
    for p in paths + (REQS, LOGS):
        try:
            os.makedirs(p, exist_ok=True) if p in (REQS, LOGS) else None
            os.chown(p, 10001, 10001)
        except OSError:
            pass


def _audit(action, target, **kw):
    try:
        from engine.supervisor import audit
        audit("orch_" + action, target, **kw)
    except Exception:
        pass


def _day(t):
    return time.strftime("%Y-%m-%d", time.localtime(t))


def _agent_state(s, name):
    a = s["agents"].setdefault(name, {})
    a.setdefault("paused", False)
    return a


def enqueue(s, agent, key=None, payload=None, by="schedule", now=None, cooldown=0):
    """Add a task unless one with the same key is still open (or finished less than `cooldown` s ago).
    Returns the task (new or existing)."""
    now = now or _now()
    key = key or agent
    for t in s["tasks"].values():
        if t["key"] == key and (t["state"] in OPEN or now - t["updated"] < cooldown):
            return t
    tid = f"{agent}-{int(now * 1000)}-{len(s['tasks'])}"
    t = {"id": tid, "agent": agent, "key": key, "payload": payload or {}, "state": "queued", "attempts": 0,
         "created": now, "updated": now, "not_before": now, "by": by}
    s["tasks"][tid] = t
    _audit("enqueue", tid, agent=agent, by=by)
    return t


def _set(t, state, now, **kw):
    t.update(state=state, updated=now, **kw)


def _fail(s, t, now, why):
    """Retry with backoff (60 s, 120 s, 240 s ...) until max attempts, then dead-letter as failed."""
    spec = REGISTRY.get(t["agent"], {})
    if t["attempts"] < spec.get("attempts", 3):
        _set(t, "queued", now, not_before=now + 60 * 2 ** (t["attempts"] - 1), last_error=why[:200])
        _audit("retry", t["id"], why=why[:120], attempts=t["attempts"])
    else:
        _set(t, "failed", now, last_error=why[:200], finished=now)
        _audit("dead", t["id"], why=why[:120], attempts=t["attempts"])


def reap(s, now=None):
    """Collect finished children, kill overdue ones, requeue leases this process does not own (lost on restart)."""
    now = now or _now()
    for t in s["tasks"].values():
        if t["state"] != "leased":
            continue
        p = _PROCS.get(t["id"])
        if p is None:
            if t.get("kind") == "proc" or now > t.get("lease_until", 0):
                _fail(s, t, now, "lease lost (supervisor restarted)")
            continue
        proc, log = p
        rc = proc.poll()
        if rc is None:
            if now > t.get("lease_until", 0):
                proc.kill()
                _PROCS.pop(t["id"], None)
                log.close()
                _fail(s, t, now, f"timed out after {REGISTRY[t['agent']]['timeout']} s")
            continue
        _PROCS.pop(t["id"], None)
        log.close()
        tail = _tail(t["id"])
        if rc == 0:
            _set(t, "done", now, rc=0, result=tail, finished=now)
            _audit("done", t["id"], result=tail[:120])
        else:
            _fail(s, t, now, f"rc {rc}: {tail}")


def _tail(tid):
    try:
        lines = open(os.path.join(LOGS, tid + ".log"), encoding="utf-8", errors="replace").read().strip().splitlines()
        return (lines[-1] if lines else "")[:200]
    except OSError:
        return ""


def schedule(s, now=None, imap=False):
    """Queue each periodic agent that is due. Daily agents chain with "after" (outreach waits for hn today)."""
    now = now or _now()
    lt = time.localtime(now)
    for name, spec in REGISTRY.items():
        if spec.get("imap") and not imap:
            continue
        a = _agent_state(s, name)
        if spec.get("every"):
            if now - a.get("last_queued", 0) >= spec["every"]:
                enqueue(s, name, now=now)
                a["last_queued"] = now
        elif spec.get("at_hour") is not None:
            if lt.tm_hour < spec["at_hour"] or a.get("day_queued") == _day(now):
                continue
            dep = spec.get("after")
            if dep and _agent_state(s, dep).get("day_done") != _day(now):
                continue
            enqueue(s, name, key=f"{name}:{_day(now)}", now=now)
            a["day_queued"] = _day(now)


def from_plan(s, plan, now=None):
    """Shadow's plan (engine/agents.py) -> tasks. Locked actions are queued too and wait as held, so the
    control room shows what Shadow would do; scale stays with the governor."""
    now = now or _now()
    keys = set()
    for a in plan or []:
        agent = PLAN_AGENT.get(a.get("action"))
        if agent and a.get("target"):
            key = f"{agent}:{a['target']}"
            keys.add(key)
            enqueue(s, agent, key=key, payload={"target": a["target"], "why": a.get("why")}, by="shadow plan",
                    now=now, cooldown=PLAN_COOLDOWN)
    for tid, t in list(s["tasks"].items()):  # no longer in the plan (answered, submitted, gone): drop it unrun
        if t.get("by") == "shadow plan" and t["state"] in ("queued", "held") and t["key"] not in keys:
            del s["tasks"][tid]
    return len(keys)


def blocked(s, t, level, now=None):
    """Why this task may not run now, or None."""
    now = now or _now()
    spec = REGISTRY.get(t["agent"])
    if spec is None:
        return "unknown agent"
    if os.path.exists(os.path.join(WORKSPACE, "KILL")):
        return "kill switch on"
    a = _agent_state(s, t["agent"])
    if a.get("paused"):
        return "paused by operator"
    if level < spec.get("needs", 0):
        return f"needs Shadow level {spec['needs']} (now {level})"
    if a.get("runs_day") == _day(now) and a.get("runs", 0) >= spec.get("budget", 10 ** 6):
        return f"daily budget {spec['budget']} spent"
    if t.get("not_before", 0) > now:
        return "backing off"
    return None


def _start(s, t, now, fns):
    spec = REGISTRY[t["agent"]]
    a = _agent_state(s, t["agent"])
    if a.get("runs_day") != _day(now):
        a.update(runs_day=_day(now), runs=0)
    a["runs"] = a.get("runs", 0) + 1
    t["attempts"] += 1
    _set(t, "leased", now, kind=spec["kind"], lease_until=now + spec["timeout"], started=now, held=None)
    _audit("start", t["id"], attempt=t["attempts"])
    if spec["kind"] == "fn":
        try:
            out = (fns or FNS)[spec["fn"]](t["payload"])
            _set(t, "done", now, rc=0, result=str(out)[:200], finished=now)
            _audit("done", t["id"], result=str(out)[:120])
        except Exception as e:
            _fail(s, t, now, f"{type(e).__name__}: {e}")
        return
    os.makedirs(LOGS, exist_ok=True)
    log = open(os.path.join(LOGS, t["id"] + ".log"), "w", encoding="utf-8")
    try:
        from engine.supervisor import _as_engine_user
        pre = _as_engine_user if os.name != "nt" else None
    except Exception:
        pre = None
    proc = subprocess.Popen([sys.executable, "-m", "engine", *spec["argv"]], stdout=log, stderr=subprocess.STDOUT,
                            preexec_fn=pre)
    _PROCS[t["id"]] = (proc, log)


def dispatch(s, level, now=None, fns=None):
    """Start queued tasks (oldest first) while fewer than MAX_PROCS children run; mark the rest held with why."""
    now = now or _now()
    started = 0
    for t in sorted((t for t in s["tasks"].values() if t["state"] in ("queued", "held")), key=lambda t: t["created"]):
        why = blocked(s, t, level, now)
        if why:
            if t["state"] != "held" or t.get("held") != why:
                _set(t, "held", now, held=why)
            continue
        if REGISTRY[t["agent"]]["kind"] == "proc" and len(_PROCS) >= MAX_PROCS:
            continue
        _start(s, t, now, fns)
        started += 1
    return started


def _mark_days(s, now):
    for t in s["tasks"].values():
        if t["state"] == "done" and t.get("finished", 0) and _day(t["finished"]) == _day(now):
            _agent_state(s, t["agent"])["day_done"] = _day(now)


def prune(s, now=None):
    now = now or _now()
    for tid in [k for k, t in s["tasks"].items() if t["state"] in ("done", "failed") and now - t["updated"] > KEEP_S]:
        del s["tasks"][tid]


def tick(imap=False, now=None, plan=None, level=None, fns=None, path=None):
    """One orchestrator pass (the supervisor calls it every 15 s). Inputs are injectable for tests."""
    now = now or _now()
    s = load(path)
    apply_requests(s, now, reqs=os.path.join(os.path.dirname(path), "requests") if path else None)
    reap(s, now)
    _mark_days(s, now)
    schedule(s, now, imap)
    if level is None:
        try:
            from engine import shadow_brain
            level = shadow_brain.ladder()["level"]
        except Exception:
            level = 1
    if plan is None:
        try:
            from engine import agents
            plan = agents.plan(level=level)
        except Exception:
            plan = []
    from_plan(s, plan, now)
    dispatch(s, level, now, fns)
    prune(s, now)
    s.update(ts=now, level=level, running=len(_PROCS))
    save(s, path)
    return s


# ---- in-process agents (fast; anything slow is a "proc" agent) ----
def shadow_retry(payload):
    from engine import shadow
    return f"retried {shadow._retry_as_shadow([payload['target']])}"


def requeue_batch(payload):
    from engine.supervisor import requeue_stale
    return f"requeued {requeue_stale()}"


FNS = {"shadow_retry": shadow_retry, "requeue_batch": requeue_batch}


def enabled():
    return os.environ.get("REGEN_ORCH", "1") != "0"


def status(path=None):
    s = load(path)
    tasks = sorted(s["tasks"].values(), key=lambda t: t["updated"], reverse=True)
    return {"ts": s.get("ts"), "level": s.get("level"), "running": s.get("running", 0),
            "agents": {n: {**{k: v for k, v in spec.items() if k in ("kind", "every", "at_hour", "needs", "budget", "why")},
                           **_agent_state(s, n)} for n, spec in REGISTRY.items()},
            "open": [t for t in tasks if t["state"] in OPEN],
            "recent": [t for t in tasks if t["state"] in ("done", "failed")][:20]}


REQS = os.path.join(DIR, "requests")


def command(action, name, by="operator", reqs=None):
    """run (queue one now) | pause | resume one agent. Raises ValueError on a bad action or agent. The supervisor
    stays the only writer of state.json: this drops a request file that its next tick applies (<= 15 s)."""
    if action not in ("run", "pause", "resume"):
        raise ValueError("action must be run, pause or resume")
    if name not in REGISTRY:
        raise ValueError(f"unknown agent {name!r}; agents: {', '.join(REGISTRY)}")
    reqs = reqs or REQS
    os.makedirs(reqs, exist_ok=True)
    rid = f"{int(_now() * 1000)}-{os.getpid()}-{name}"
    tmp = os.path.join(reqs, rid + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"action": action, "agent": name, "by": by, "ts": _now()}, f)
    os.replace(tmp, os.path.join(reqs, rid + ".json"))
    return {"request": rid, "action": action, "agent": name, "note": "the supervisor applies it within 15 s"}


def apply_requests(s, now=None, reqs=None):
    """Fold operator requests (command()) into the state, oldest first, and delete them. Returns how many."""
    now, reqs, n = now or _now(), reqs or REQS, 0
    try:
        files = sorted(f for f in os.listdir(reqs) if f.endswith(".json"))
    except OSError:
        return 0
    for f in files:
        path = os.path.join(reqs, f)
        try:
            r = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            r = {}
        try:
            os.remove(path)
        except OSError:
            pass
        name, action, by = r.get("agent"), r.get("action"), r.get("by") or "operator"
        if name not in REGISTRY:
            continue
        if action == "run":
            enqueue(s, name, key=f"{name}:manual:{f}", by=by, now=now)
        elif action in ("pause", "resume"):
            _agent_state(s, name)["paused"] = action == "pause"
            _audit(action, name, by=by)
        n += 1
    return n


def main(argv):
    cmd = argv[0] if argv else "status"
    if cmd in ("run", "pause", "resume"):
        try:
            print(command(cmd, argv[1] if len(argv) > 1 else ""))
        except ValueError as e:
            print(e)
        return
    st = status()
    print(f"orchestrator: level {st['level']}, {st['running']} running, {len(st['open'])} open, last tick "
          + (time.strftime('%H:%M:%S', time.localtime(st['ts'])) if st['ts'] else "never"))
    for n, a in st["agents"].items():
        when = f"every {a['every'] // 3600} h" if a.get("every") else (f"daily after {a['at_hour']}:00" if a.get("at_hour") is not None else "on demand / plan")
        print(f"  {n:<15} {when:<18} needs L{a.get('needs', 0)}  runs today {a.get('runs', 0) if a.get('runs_day') == _day(_now()) else 0}/{a.get('budget')}"
              + ("  PAUSED" if a.get("paused") else ""))
    for t in st["open"][:15]:
        print(f"  open  {t['id']:<34} {t['state']:<7} {t.get('held') or ''}")
    for t in st["recent"][:10]:
        print(f"  {t['state']:<5} {t['id']:<34} {(t.get('result') or t.get('last_error') or '')[:70]}")
