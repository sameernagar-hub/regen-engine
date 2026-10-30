"""Fleet supervisor: every container writes a small heartbeat into the shared workspace, and fleet() reads them back
with the batch queue, so the control room can show container health without the Docker socket (mounting it would
hand every container root on the host).

  workspace/fleet/<role>_<host>.json   {"role", "host", "ts", "state", ...}   (atomic replace, one file per process)

Roles: pipeline (pass number, next scan), applier (watching / applying <batch>), relay (last POST from the Gmail tab,
codes written). A heartbeat older than STALE seconds reads as "down".

    python -m engine fleet        prints the same summary as GET /api/control/fleet
    python -m engine supervise    the supervisor container: autoscale appliers, requeue lost claims, IMAP codes
    python -m engine supervise --kill REASON | --clear | --scale LO HI | --audit N | --quarantine | --status
                                  one-shot control verbs (run inside the supervisor container; JSON out). The MCP
                                  tools fleet_status / kill / clear_kill / scale / audit_log / quarantine_list call
                                  these through `docker exec`, because the host's workspace/ is not the bank.

Autoscaling (the `supervisor` service in deploy/bank.compose.yml): compose creates REGEN_MAX_APPLIERS applier
containers; the supervisor keeps as many RUNNING as there are batches waiting or being applied (min
REGEN_MIN_APPLIERS), starting stopped ones when work arrives and stopping only appliers whose heartbeat says
"watching" (never one in the middle of a form). It talks to the Docker Engine API over /var/run/docker.sock, which
is mounted into this one container only (the socket is root-equivalent on the host: nothing else gets it).
"""
import json, os, re, socket, time

from engine.config import WORKSPACE

FLEET = os.path.join(WORKSPACE, "fleet")
BOX = os.path.join(WORKSPACE, "batches")
STALE = {"applier": 120, "relay": 120, "pipeline": 30 * 60, "reposync": 5 * 60, "answers": 120, "feedback": 30 * 60}  # pipeline sleeps between passes; it beats on wake-up
CLAIM_STALE = 45 * 60  # a claimed batch older than this with no live applier on it was lost with its container


def beat(role, **state):
    """Write this process's heartbeat. Never raises: health reporting must not stop the engine. O(1)."""
    try:
        os.makedirs(FLEET, exist_ok=True)
        host = socket.gethostname()
        path = os.path.join(FLEET, f"{role}_{host}.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dict(state, role=role, host=host, ts=time.time()), f)
        os.replace(tmp, path)
    except OSError:
        pass


def _count(d, suffix=".json"):
    try:
        return [n for n in os.listdir(d) if n.endswith(suffix) and not n.startswith(".")]
    except OSError:
        return []


def fleet(now=None):
    """Heartbeats + queue: {members: [...], inbox, claimed, done, stale_claims, codes_waiting, verdict}. O(files)."""
    now = now or time.time()
    members = []
    for n in _count(FLEET):
        try:
            m = json.load(open(os.path.join(FLEET, n), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        age = now - m.get("ts", 0)
        if age > 900:
            continue  # a recreated container gets a new hostname; the old one never beats again
        m["age"] = round(age)
        m["up"] = age <= STALE.get(m.get("role"), 120)
        members.append(m)
    # one container per singleton service: a recreated one leaves its old heartbeat behind for up to 15 min, which
    # read as two pipelines (10-18). Keep the newest per role; appliers are many, so each keeps its own row.
    top = {}
    for m in members:
        if m.get("role") != "applier" and m.get("ts", 0) > top.get(m.get("role"), {}).get("ts", -1):
            top[m.get("role")] = m
    members = [m for m in members if m.get("role") == "applier" or top.get(m.get("role")) is m]
    members.sort(key=lambda m: (m.get("role", ""), m.get("host", "")))
    claimed = _count(os.path.join(BOX, "claimed"))
    busy = {m.get("batch") for m in members if m.get("role") == "applier" and m["up"]}
    stale = [n for n in claimed if n not in busy
             and now - os.path.getmtime(os.path.join(BOX, "claimed", n)) > CLAIM_STALE]
    waiting = [n[:-5] for n in _count(os.path.join(WORKSPACE, "codes"), ".wait")
               if not os.path.exists(os.path.join(WORKSPACE, "codes", n[:-5] + ".txt"))]
    relay = next((m for m in members if m.get("role") == "relay"), None)
    problems = []
    if not any(m["up"] for m in members if m.get("role") == "applier"):
        problems.append("no applier is alive")
    if not any(m["up"] for m in members if m.get("role") == "pipeline"):
        problems.append("pipeline is not running")
    tab_age = now - relay["last_post"] if relay and relay.get("last_post") else None
    imap = any(m["up"] and m.get("imap") for m in members if m.get("role") == "supervisor")
    if not imap and (tab_age is None or tab_age > 120):
        problems.append("Gmail tab is not posting codes (re-paste gmail_relay.js; keep the tab active)")
    sup = next((m for m in members if m.get("role") == "supervisor" and m["up"]), None)
    for name, st in ((sup or {}).get("services") or {}).items():
        if st != "ok":
            problems.append(f"{name}: {st}")
    if stale:
        problems.append(f"{len(stale)} claimed batch(es) lost with their container: python scripts/requeue.py --stale")
    return {"members": members, "inbox": len(_count(os.path.join(BOX, "inbox"))), "claimed": len(claimed),
            "done": len(_count(os.path.join(BOX, "done"))), "stale_claims": stale, "codes_waiting": waiting,
            "gmail_tab_age": round(tab_age) if tab_age is not None else None, "imap_codes": imap, "problems": problems,
            "verdict": "ok" if not problems else "attention"}


# ---------------- supervisor container ----------------
SOCK = "/var/run/docker.sock"


def _docker(method, path, body=None):
    """One Docker Engine API call over the unix socket (stdlib only). Returns parsed JSON or None."""
    import http.client, socket as so
    class C(http.client.HTTPConnection):
        def connect(self):
            self.sock = so.socket(so.AF_UNIX, so.SOCK_STREAM); self.sock.connect(SOCK)
    c = C("docker", timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None,
              {"Content-Type": "application/json"} if body is not None else {})
    r = c.getresponse(); body = r.read()
    try:
        return json.loads(body) if body else None
    except ValueError:
        return None


def appliers():
    """[(id, name, running)] for this compose project's applier containers, by container number."""
    import urllib.parse
    labels = ["com.docker.compose.service=applier"]  # this stack only: never another project's containers
    if os.environ.get("REGEN_COMPOSE_PROJECT"):
        labels.append("com.docker.compose.project=" + os.environ["REGEN_COMPOSE_PROJECT"])
    flt = urllib.parse.quote(json.dumps({"label": labels}))
    rows = _docker("GET", f"/containers/json?all=1&filters={flt}") or []
    return sorted(((r["Id"], r["Names"][0].lstrip("/"), r["State"] == "running") for r in rows), key=lambda x: x[1])


def _jobs(d):
    n = 0
    for f in _count(d):
        try:
            n += len(json.load(open(os.path.join(d, f), encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return n


def desired(lo, hi, per_applier=3):
    """Appliers needed now: one per `per_applier` jobs waiting in inbox/ or being applied in claimed/."""
    jobs = _jobs(os.path.join(BOX, "inbox")) + _jobs(os.path.join(BOX, "claimed"))
    return max(lo, min(hi, -(-jobs // per_applier))), jobs


def drain_path(host):
    """workspace/fleet/drain_<host>: the supervisor asks one applier to stop claiming (engine/apply/worker.py)."""
    return os.path.join(FLEET, f"drain_{host}")


def _expired(cid):
    """True when enforce() wrote this drain because the container outlived TTL: such a drain is never cancelled."""
    try:
        return open(drain_path(cid[:12]), encoding="utf-8").read().startswith("expire")
    except OSError:
        return False


def scale(lo, hi, idle_grace=180, _idle={}):  # _idle: first time each container was seen idle (kept across calls)
    """Start/create appliers up to desired(); retire idle ones above it. O(containers).

    Retiring is a handshake, never a stop on a heartbeat alone: a heartbeat can say "watching" a moment before the
    worker claims a batch, and `docker stop` takes up to 20 s (10-12: an applier claimed a batch inside that window
    and died holding it). So the supervisor writes drain_<host>, the worker checks it BEFORE every claim and answers
    with state "draining", and only a container whose heartbeat says "draining" is stopped and deleted. More work
    arriving cancels pending drains first."""
    want, jobs = desired(lo, hi)
    rows = appliers()
    running = [r for r in rows if r[2]]
    beats = {m["host"]: m for m in fleet()["members"] if m.get("role") == "applier"}
    now = time.time()
    drains = [r for r in running if os.path.exists(drain_path(r[0][:12]))]  # a container's hostname is its short id
    active = [r for r in running if r not in drains]
    if len(active) < want:
        need = want - len(active)
        for r in [d for d in drains if not _expired(d[0])][:need]:  # cancel a drain before adding a container
            os.remove(drain_path(r[0][:12]))
            drains.remove(r)
            need -= 1
        stopped = [r for r in rows if not r[2]]
        for cid, name, _ in stopped[:need]:
            _docker("POST", f"/containers/{cid}/start")
            audit("start", name, jobs=jobs, want=want)
        for _ in range(max(0, need - len(stopped))):  # none left to start: create one
            if running:
                try:
                    audit("create", clone(running[0][0], appliers()), jobs=jobs, want=want)
                except Refused as ex:  # a guardrail said no: say why once per pass, create nothing else
                    audit("refuse", "create applier", reason=str(ex)[:120], jobs=jobs, want=want)
                    break
    elif len(active) > want:
        for cid, name, up in reversed(active[:]):
            if len(active) <= want:
                break
            m = beats.get(cid[:12])
            if len(active) > hi:
                # 10-21: above the gear's cap (a downshift with batches waiting) no applier ever idles, so the extras
                # ran on at full CPU. Drain now: the worker finishes its batch, then stops claiming (handshake above).
                os.makedirs(FLEET, exist_ok=True)
                open(drain_path(cid[:12]), "w").write(str(now))
                active.remove((cid, name, up))
                _idle.pop(cid, None)
            elif m and m["up"] and m.get("state") == "watching":
                first = _idle.setdefault(cid, now)
                if now - first >= idle_grace:
                    os.makedirs(FLEET, exist_ok=True)
                    open(drain_path(cid[:12]), "w").write(str(now))
                    active.remove((cid, name, up))
                    _idle.pop(cid, None)
            else:
                _idle.pop(cid, None)
    for cid, name, up in drains:  # retire only what the worker confirmed: it can no longer claim anything
        m = beats.get(cid[:12])
        if m and m.get("state") == "draining":
            others = [r for r in running if r[0] != cid and r not in drains and (beats.get(r[0][:12]) or {}).get("up")]
            if len(others) < max(lo, 1):  # 10-19: gear N asks for 0-0; one stays as the clone source
                # 10-17: a compose recreate racing scale() left a drain on the last applier, it was removed, and with
                # no running applier left to clone from nothing could ever be created again (batches sat in the inbox).
                # Retire only while `lo` other appliers are up (live heartbeat, not draining); else un-drain it (an
                # expired one waits until its replacement runs).
                if not _expired(cid):
                    try:
                        os.remove(drain_path(cid[:12]))
                    except OSError:
                        pass
                    audit("keep", name, reason=f"minimum {max(lo, 1)}", jobs=jobs, want=want)
                continue
            _docker("POST", f"/containers/{cid}/stop?t=20")
            _docker("DELETE", f"/containers/{cid}")  # idle capacity is removed, not parked
            try:
                os.remove(drain_path(cid[:12]))
            except OSError:
                pass
            running = [r for r in running if r[0] != cid]
            audit("remove", name, jobs=jobs, want=want)
    return want, len(running), jobs


def requeue_stale():
    """Claims lost with a dead container go back to the inbox, minus jobs that reached a final status."""
    from engine.apply.worker import DIRS
    from engine.pipeline import latest_status
    f = fleet()
    if not f["stale_claims"]:
        return 0
    st = latest_status()
    from engine.feedback.events import read
    done = {(e.get("job") or "").lower().strip() for e in read("application")  # the same role under another URL
            if not e.get("dry") and (e.get("status") or "").startswith("SUBMITTED")}
    for n in f["stale_claims"]:
        src = os.path.join(DIRS["claimed"], n)
        try:
            jobs = [j for j in json.load(open(src, encoding="utf-8")) if st.get(j["url"]) not in ("SUBMITTED", "SKIPPED")
                    and j.get("name", "").lower().strip() not in done]
            tmp = os.path.join(DIRS["inbox"], ".re_" + n)
            json.dump(jobs, open(tmp, "w", encoding="utf-8"), indent=1)
            os.replace(tmp, os.path.join(DIRS["inbox"], "re_" + n))
            os.remove(src)
            if os.path.exists(src + ".lock"):
                os.remove(src + ".lock")
            print(f"requeue: {n} -> inbox ({len(jobs)} jobs)", flush=True)
        except (OSError, ValueError) as e:
            print(f"requeue: {n} skipped: {e}", flush=True)
    return len(f["stale_claims"])


def audit(action, target, **kw):
    """Every supervisor action goes to the ledger (kind "supervisor") and stdout: nothing happens untracked."""
    print(f"supervisor: {action} {target} {kw or ''}".rstrip(), flush=True)
    try:
        from engine.feedback.events import record
        record("supervisor", action=action, target=str(target)[:120], **kw)
    except Exception:
        pass


PROC = "/proc"  # the Docker VM's view: a container reads the VM's meminfo and loadavg
MIN_FREE_MB = int(os.environ.get("REGEN_MIN_FREE_MB", "2048"))  # leave this much VM memory for everything else
MAX_LOAD = float(os.environ.get("REGEN_MAX_LOAD", "0.7"))  # 1-min load per CPU above which nothing new starts


def headroom(proc=None):
    """None when the machine can take one more applier (~1.6 cores, ~0.8 GB), else the reason it cannot. 10-21: 9
    appliers held the VM at 900% CPU and 6.5 of 7.6 GB. Unreadable /proc (not Linux) says nothing. O(1)."""
    proc = proc or PROC
    try:
        mem = {k: int(v.split()[0]) for k, v in (l.split(":", 1) for l in open(os.path.join(proc, "meminfo")))}
        load = float(open(os.path.join(proc, "loadavg")).read().split()[0])
    except (OSError, ValueError, IndexError):
        return None
    free_mb, cpus = mem.get("MemAvailable", 0) // 1024, os.cpu_count() or 1
    if free_mb - 800 < MIN_FREE_MB:
        return f"low memory: {free_mb} MB free, keeping {MIN_FREE_MB} MB"
    if load / cpus > MAX_LOAD:
        return f"high CPU: load {load:.1f} on {cpus} CPUs (max {MAX_LOAD:.0%})"
    return None


def clone(cid, rows):
    """Create and start a new applier from a running one's config (same image, env, volumes, limits, compose labels).
    Refuses when headroom() says the machine is busy. Returns the new container's name. O(1) API calls."""
    why = headroom()
    if why:
        raise Refused(why)
    i = _docker("GET", f"/containers/{cid}/json")
    used = {int(n.rsplit("-", 1)[1]) for _, n, _ in rows if n.rsplit("-", 1)[-1].isdigit()}
    n = next(k for k in range(1, 100) if k not in used)
    name = re.sub(r"-\d+$", f"-{n}", i["Name"].lstrip("/"))
    labels = dict(i["Config"].get("Labels") or {}, **{"com.docker.compose.container-number": str(n)})
    hc = {k: i["HostConfig"].get(k) for k in ("Binds", "Mounts", "ShmSize", "NanoCpus", "Memory", "RestartPolicy",
                                              "NetworkMode", "SecurityOpt", "CapDrop", "ReadonlyRootfs", "PidsLimit")
          if i["HostConfig"].get(k) is not None}
    nets = {k: {"Aliases": [f"applier-{n}"]} for k in (i["NetworkSettings"].get("Networks") or {})}
    body = {"Image": i["Config"]["Image"], "Env": i["Config"].get("Env"), "Entrypoint": i["Config"].get("Entrypoint"),
            "Cmd": i["Config"].get("Cmd"), "User": i["Config"].get("User"), "Labels": labels, "HostConfig": hc,
            "NetworkingConfig": {"EndpointsConfig": nets}}
    body = bound(body, len(rows))  # raises Refused: nothing unbounded or outside the allowlist is ever created
    new = _docker("POST", f"/containers/create?name={name}", body) or {}
    if new.get("Id"):
        _docker("POST", f"/containers/{new['Id']}/start")
    return name


# ---------------- container guardrails ----------------
# The supervisor holds the Docker socket, so it is the one place that can create containers: everything it creates
# is bounded, labeled, counted and audited, and a container of this project that compose did not declare is stopped.
SCALABLE = {"applier", "eval"}  # the only services the supervisor may create containers for
DECLARED = {"seed", "applier", "pipeline", "relay", "supervisor", "postgres", "ledger", "mcp", "answers", "api", "web",
            "reposync", "eval", "desk", "feedback"}  # deploy/bank.compose.yml services (tests/test_v014.py keeps the two in step)
CAPS = {"applier": {"NanoCpus": int(float(os.environ.get("REGEN_APPLIER_CPUS", "1.5")) * 1e9),
                    "Memory": int(os.environ.get("REGEN_APPLIER_MEM_MB", "2048")) * 2 ** 20,
                    "PidsLimit": int(os.environ.get("REGEN_APPLIER_PIDS", "1024"))},
        "eval": {"NanoCpus": 1_000_000_000, "Memory": 1024 * 2 ** 20, "PidsLimit": 256}}
TTL = float(os.environ.get("REGEN_APPLIER_TTL_H", "12")) * 3600  # a supervisor-made applier is recycled after this
MANAGED = "regen.managed-by"  # label on every container the supervisor creates


class Refused(Exception):
    """A guardrail refused to create a container (the reason is audited)."""


def bound(body, existing):
    """The create request, bounded: allowlisted service, under HARD_MAX containers, CPU/memory/pids at or below the
    service caps (missing = the cap), never privileged, never the Docker socket, labeled as supervisor-made with a
    creation time. Raises Refused otherwise. O(binds)."""
    labels = dict(body.get("Labels") or {})
    svc = labels.get("com.docker.compose.service")
    if svc not in SCALABLE:
        raise Refused(f"service {svc!r} is not scalable (allowlist: {sorted(SCALABLE)})")
    if existing >= HARD_MAX:
        raise Refused(f"{existing} {svc} containers already (hard max {HARD_MAX})")
    hc = dict(body.get("HostConfig") or {})
    mounts = [str(b) for b in hc.get("Binds") or []] + [str(m.get("Source", "")) for m in hc.get("Mounts") or []]
    if any("docker.sock" in m for m in mounts):
        raise Refused("the Docker socket is never mounted into a created container")
    for k, cap in CAPS[svc].items():
        hc[k] = min(hc[k], cap) if hc.get(k) else cap  # 0 / missing means unlimited to Docker: never allowed
    hc["Privileged"] = False
    hc.pop("CapAdd", None)
    labels.update({MANAGED: "supervisor", "regen.created": str(int(time.time()))})
    return dict(body, Labels=labels, HostConfig=hc)


def enforce(now=None):
    """Every pass: stop any container of this project whose service compose does not declare; give a scalable
    container without CPU/memory limits its caps (live `docker update`); drain supervisor-made appliers older than
    TTL (the drain handshake in scale() stops them once idle, and a fresh one replaces them if work is waiting).
    Returns the actions taken, each audited. O(containers)."""
    import urllib.parse
    now = now or time.time()
    proj = os.environ.get("REGEN_COMPOSE_PROJECT", "deploy")
    flt = urllib.parse.quote(json.dumps({"label": [f"com.docker.compose.project={proj}"]}))
    acts = []
    for r in _docker("GET", f"/containers/json?all=1&filters={flt}") or []:
        lab, name = r.get("Labels") or {}, (r.get("Names") or ["/?"])[0].lstrip("/")
        svc = lab.get("com.docker.compose.service")
        if svc not in DECLARED:
            if r.get("State") == "running":
                _docker("POST", f"/containers/{r['Id']}/stop?t=10")
                audit("refuse", name, reason=f"service {svc!r} is not declared in the compose file: stopped")
                acts.append(("stop", name))
            continue
        if svc != "applier" or r.get("State") != "running":  # eval containers are bounded at create and short-lived
            continue
        hc = (_docker("GET", f"/containers/{r['Id']}/json") or {}).get("HostConfig") or {}
        fix = {k: cap for k, cap in CAPS[svc].items() if not hc.get(k) or hc[k] > cap}
        if fix:
            _docker("POST", f"/containers/{r['Id']}/update", fix)
            audit("bound", name, **{k.lower(): v for k, v in fix.items()})
            acts.append(("bound", name))
        made = lab.get("regen.created")
        if lab.get(MANAGED) == "supervisor" and made and made.isdigit() and now - int(made) > TTL \
                and not os.path.exists(drain_path(r["Id"][:12])):
            os.makedirs(FLEET, exist_ok=True)
            open(drain_path(r["Id"][:12]), "w").write(f"expire {now}")
            audit("expire", name, age_h=round((now - int(made)) / 3600, 1))
            acts.append(("expire", name))
    return acts


def prune_images():
    """Remove dangling images (old builds no container uses): frees disk; images in use are never touched."""
    import urllib.parse
    r = _docker("POST", "/images/prune?filters=" + urllib.parse.quote(json.dumps({"dangling": ["true"]}))) or {}
    if r.get("ImagesDeleted"):
        audit("prune", f"{len(r['ImagesDeleted'])} dangling images", freed_mb=round((r.get("SpaceReclaimed") or 0) / 1e6))


# ---------------- leak guard + kill switch ----------------
_scanned = {}
TEXT_DIRS = ("logs", "outreach", os.path.join("batches", "done"), "specs", "")  # appended or rewritten text files
PDF_DIRS = ("out",)  # tailored resumes: their extracted text, once per file version (proof/ is PNG only)


def guard():
    """Scan files written since the last pass (logs, outreach, finished batches, resume specs, top-level ledger
    files, and the text of new resume PDFs) for secret values from .env and secret shapes (engine/guard.py).
    A hit is a kill: kill() + the file moved to quarantine/ (kept for review, never deleted automatically) + an
    audit record naming the file and rule (never the secret). O(new bytes) + one PDF read per new resume."""
    import shutil
    from engine import guard as G
    secrets = G.secrets()
    hits = []
    for sub in TEXT_DIRS:
        d = os.path.join(WORKSPACE, sub)
        if not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            p = os.path.join(d, n)
            if not os.path.isfile(p) or not n.endswith((".log", ".json", ".jsonl", ".md", ".txt")):
                continue
            size = os.path.getsize(p)
            start = _scanned.get(p, 0) if _scanned.get(p, 0) <= size else 0
            if size == start:
                continue
            with open(p, "rb") as f:
                f.seek(start)
                text = f.read().decode("utf-8", "replace")
            _scanned[p] = size
            rule = G.secret_rule(text, secrets)
            if rule:
                hits.append((p, rule))
    for sub in PDF_DIRS:
        d = os.path.join(WORKSPACE, sub)
        if not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            p = os.path.join(d, n)
            if not n.endswith(".pdf") or not os.path.isfile(p):
                continue
            ver = (os.path.getsize(p), os.path.getmtime(p))
            if _scanned.get(p) == ver:
                continue
            _scanned[p] = ver
            rule = G.secret_rule(G.pdf_text(p), secrets)
            if rule:
                hits.append((p, rule))
    for p, rule in hits:
        kill(f"secret ({rule}) in {os.path.relpath(p, WORKSPACE)}")
        q = os.path.join(WORKSPACE, "quarantine")
        os.makedirs(q, exist_ok=True)
        shutil.move(p, os.path.join(q, f"{int(time.time())}_{os.path.basename(p)}"))
    return hits


def kill_files(reason):
    """The part of the kill switch that needs no Docker socket: KILL + batches/STOP. Every step honors it (pipeline
    before scan/build/dispatch, runner before each submit, workers before each claim, answers, reposync)."""
    for n in (os.path.join("batches", "STOP"), "KILL"):
        p = os.path.join(WORKSPACE, n)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {reason}\n")


def kill(reason):
    """The kill switch: workers stop after their current step (batches/STOP), appliers and the pipeline are stopped
    now, the supervisor holds (KILL) and the reason is recorded. After investigating:
    docker exec deploy-supervisor-1 python -m engine supervise --clear"""
    import urllib.parse
    kill_files(reason)
    try:
        for cid, name, up in appliers():
            if up:
                _docker("POST", f"/containers/{cid}/stop?t=10")
        flt = urllib.parse.quote(json.dumps({"label": ["com.docker.compose.service=pipeline"]}))
        for r in _docker("GET", f"/containers/json?filters={flt}") or []:
            _docker("POST", f"/containers/{r['Id']}/stop?t=10")
    except Exception as ex:
        print(f"supervisor: kill could not stop containers: {ex}", flush=True)
    audit("KILL", reason)


LIMITS = os.path.join(WORKSPACE, "fleet_limits.json")
HARD_MAX = 12  # never more appliers than this, whatever the override says (one machine, one Gmail inbox)


def limits(lo, hi):
    """(min, max) appliers: the gearbox (engine/gearbox.py) when a gear is set, else `supervise --scale`'s override,
    else the env defaults."""
    from engine.gearbox import appliers
    g = appliers()
    if g is not None:
        return _clamp(*g)
    try:
        o = json.load(open(LIMITS, encoding="utf-8"))
        lo, hi = int(o["min"]), int(o["max"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return _clamp(lo, hi)


def _clamp(lo, hi):
    hi = max(0, min(HARD_MAX, hi))
    return max(0, min(lo, hi)), hi


def audit_tail(n=30):
    """The last n supervisor events (kind "supervisor") from the ledger, newest last. O(file) but read backwards."""
    from engine.feedback.events import _path
    out = []
    try:
        with open(_path(), "rb") as f:
            f.seek(0, 2)
            pos, buf = f.tell(), b""
            while pos > 0 and len(out) < n:
                step = min(65536, pos)
                pos -= step
                f.seek(pos)
                buf = f.read(step) + buf
                lines = buf.split(b"\n")
                buf = lines[0]
                if pos == 0:  # start of file: the first line is complete too
                    lines, buf = [b""] + lines, b""
                for line in reversed(lines[1:]):
                    if b'"supervisor"' in line:
                        try:
                            e = json.loads(line)
                        except ValueError:
                            continue
                        if e.get("kind") == "supervisor":
                            out.append(e)
                            if len(out) >= n:
                                break
    except OSError:
        pass
    return out[::-1]


def quarantine_list():
    """Files the leak guard moved aside (names, sizes, times; never contents: they may hold the secret)."""
    q = os.path.join(WORKSPACE, "quarantine")
    if not os.path.isdir(q):
        return []
    return [{"file": n, "bytes": os.path.getsize(os.path.join(q, n)),
             "moved": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(os.path.join(q, n))))}
            for n in sorted(os.listdir(q))]


def clear_kill(by="operator"):
    removed = []
    for x in (os.path.join("batches", "STOP"), "KILL"):
        if os.path.exists(os.path.join(WORKSPACE, x)):
            os.remove(os.path.join(WORKSPACE, x))
            removed.append(x)
    started = []
    try:  # kill() stopped the pipeline container; appliers come back through scale(), the pipeline does not
        import urllib.parse
        flt = urllib.parse.quote(json.dumps({"label": ["com.docker.compose.service=pipeline"]}))
        for r in _docker("GET", f"/containers/json?all=1&filters={flt}") or []:
            if r.get("State") != "running":
                _docker("POST", f"/containers/{r['Id']}/start")
                started.append((r.get("Names") or [r["Id"][:12]])[0].lstrip("/"))
    except Exception as ex:
        print(f"supervisor: clear could not restart the pipeline: {ex}", flush=True)
    audit("clear", "kill switch", by=by, started=started)
    return removed


def status():
    f = fleet()
    k = os.path.join(WORKSPACE, "KILL")
    f["kill"] = open(k, encoding="utf-8").read().strip() if os.path.exists(k) else None
    f["containers"] = containers()
    f["limits"] = dict(zip(("min", "max"), limits(int(os.environ.get("REGEN_MIN_APPLIERS", "1")),
                                                  int(os.environ.get("REGEN_MAX_APPLIERS", "7")))))
    return f


def control(argv):
    """One-shot verbs for the operator (CLI or MCP via docker exec). Returns a JSON-able dict, or None when argv
    holds no verb. Every change is audited."""
    a = list(argv or [])
    if "--status" in a:
        return status()
    if "--kill" in a:
        reason = " ".join(a[a.index("--kill") + 1:]).strip() or "operator kill"
        kill(reason[:200])
        return {"killed": True, "reason": reason[:200]}
    if "--clear" in a:
        return {"cleared": clear_kill()}
    if "--scale" in a:
        i = a.index("--scale")
        lo, hi = _clamp(int(a[i + 1]), int(a[i + 2]))
        os.makedirs(os.path.dirname(LIMITS), exist_ok=True)
        tmp = LIMITS + ".tmp"
        json.dump({"min": lo, "max": hi}, open(tmp, "w", encoding="utf-8"))
        os.replace(tmp, LIMITS)
        audit("limits", f"{lo}..{hi}", min=lo, max=hi)
        return {"min": lo, "max": hi, "note": "the supervisor applies it within 15 s"}
    if "--audit" in a:
        i = a.index("--audit")
        n = int(a[i + 1]) if len(a) > i + 1 and a[i + 1].isdigit() else 30
        return {"audit": audit_tail(min(n, 500))}
    if "--eval" in a:  # ask for one eval container now (the supervisor launches it within a minute)
        os.makedirs(_bench_dir(), exist_ok=True)
        _own(_bench_dir())
        open(os.path.join(_bench_dir(), "REQUEST"), "w").write(str(time.time()))
        audit("eval_request", "B1-B10")
        return {"requested": True, "note": "an eval container starts within a minute; results at /evals"}
    if "--quarantine" in a:
        return {"quarantine": quarantine_list()}
    return None


# services without a heartbeat of their own: the supervisor probes them over the compose network
SERVICES = {"api": "http://api:8787/api/health", "web": "http://web:3000/", "mcp": "http://mcp:8790/mcp",
            "ledger": None, "postgres": None, "answers": None, "reposync": None,
            "desk": "http://desk:6080/",
            # 10-29 (user: "one container is always checking the mails"): liveness() only restarts a RUNNING feedback
            # whose beat went stale; a stopped one was never started again
            "feedback": None}


CONTAINERS = os.path.join(WORKSPACE, "containers.json")  # not under fleet/: those files are heartbeats


def _cpu_mem(st):
    """(cpu %, mem MiB, mem limit MiB) from one Docker stats sample (stream=false carries precpu_stats). O(1)."""
    c, pc = st.get("cpu_stats") or {}, st.get("precpu_stats") or {}
    dc = (c.get("cpu_usage") or {}).get("total_usage", 0) - (pc.get("cpu_usage") or {}).get("total_usage", 0)
    ds = c.get("system_cpu_usage", 0) - pc.get("system_cpu_usage", 0)
    n = c.get("online_cpus") or len((c.get("cpu_usage") or {}).get("percpu_usage") or []) or 1
    cpu = round(100.0 * dc / ds * n, 1) if dc > 0 and ds > 0 else 0.0
    m = st.get("memory_stats") or {}
    used = m.get("usage", 0) - ((m.get("stats") or {}).get("inactive_file") or 0)
    return cpu, round(used / 2 ** 20), round(m.get("limit", 0) / 2 ** 20)


def inventory():
    """Every container of this compose project, for the control room: service, state, uptime, health, image, CPU and
    memory (one stats sample each, fetched in parallel threads). Written to workspace/containers.json so the API
    reads it from the shared volume (only the supervisor holds the Docker socket). O(containers) calls, ~2 s."""
    import concurrent.futures as cf, urllib.parse
    proj = os.environ.get("REGEN_COMPOSE_PROJECT", "deploy")
    flt = urllib.parse.quote(json.dumps({"label": [f"com.docker.compose.project={proj}"]}))
    rows = _docker("GET", f"/containers/json?all=1&filters={flt}") or []

    def one(r):
        lab = r.get("Labels") or {}
        out = {"id": r["Id"][:12], "name": (r.get("Names") or ["/?"])[0].lstrip("/"),
               "service": lab.get("com.docker.compose.service", "?"), "state": r.get("State"),
               "status": r.get("Status"), "image": (r.get("Image") or "")[:60], "created": r.get("Created"),
               "scaled": lab.get("com.docker.compose.service") == "applier",  # appliers are the ones the supervisor creates/removes
               "managed": lab.get(MANAGED) == "supervisor", "declared": lab.get("com.docker.compose.service") in DECLARED}
        if r.get("State") == "running":
            try:
                out["cpu"], out["mem_mb"], out["mem_limit_mb"] = _cpu_mem(_docker("GET", f"/containers/{r['Id']}/stats?stream=false") or {})
            except Exception:
                pass
        return out
    with cf.ThreadPoolExecutor(8) as ex:
        items = sorted(ex.map(one, rows), key=lambda x: (x["service"], x["name"]))
    snap = {"ts": time.time(), "project": proj, "containers": items,
            "totals": {"running": sum(x["state"] == "running" for x in items), "all": len(items),
                       "cpu": round(sum(x.get("cpu", 0) for x in items), 1),
                       "mem_mb": sum(x.get("mem_mb", 0) for x in items)}}
    tmp = CONTAINERS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snap, f)
    os.replace(tmp, CONTAINERS)
    return snap


def containers(max_age=300):
    """The supervisor's last inventory (None when missing or older than max_age s: the supervisor is down)."""
    try:
        snap = json.load(open(CONTAINERS, encoding="utf-8"))
    except (OSError, ValueError):
        return None
    snap["age"] = round(time.time() - snap.get("ts", 0))
    return snap if snap["age"] <= max_age else dict(snap, stale=True)


def services(_fails={}):  # _fails: consecutive failed probes per service (kept across calls)
    """Probe each service; restart one after 3 failed probes in a row (or when its container is not running).
    Returns {service: "ok" | "down: why" | "restarted"} and puts it in the supervisor heartbeat. O(services)."""
    import urllib.error, urllib.parse, urllib.request
    out = {}
    for svc, url in SERVICES.items():
        flt = urllib.parse.quote(json.dumps({"label": [f"com.docker.compose.service={svc}"]}))
        try:
            rows = _docker("GET", f"/containers/json?all=1&filters={flt}") or []
        except Exception as ex:
            out[svc] = f"down: docker {str(ex)[:40]}"
            continue
        if not rows:
            continue  # not part of this stack
        r = rows[0]
        why = None
        if r.get("State") != "running":
            why = r.get("State") or "not running"
        elif url:
            try:
                urllib.request.urlopen(url, timeout=5).read(64)
            except urllib.error.HTTPError:
                pass  # it answered: alive (an MCP endpoint answers a plain GET with 405/406)
            except Exception as ex:
                why = str(ex)[:60]
        if not why:
            _fails.pop(svc, None)
            out[svc] = "ok"
            continue
        _fails[svc] = _fails.get(svc, 0) + 1
        if _fails[svc] >= 3 or r.get("State") in ("exited", "dead", "created"):
            _docker("POST", f"/containers/{r['Id']}/restart?t=10")
            audit("restart", svc, reason=why)
            _fails[svc] = 0
            out[svc] = "restarted"
        else:
            out[svc] = f"down: {why}"
    return out


WATCHED = ("pipeline", "answers", "relay", "reposync", "feedback")  # services that beat; appliers are matched by container id
# silence that means hung, per role: appliers beat every few seconds while they work; reposync blocks up to 30 min in
# its test gate; the answers container builds a retry batch between beats. The pipeline uses STALE (30 min).
HUNG = {"applier": 300, "relay": 300, "answers": 600, "reposync": 2400, "feedback": 1800}


def liveness(now=None, _restarted={}):  # _restarted: container id -> when this watchdog last restarted it
    """Watchdog (user, 10-18: "every container and process shows running and updates constantly"): a container that
    is up but whose process stopped beating (hung scan, frozen browser, dead thread) is restarted once its newest
    heartbeat is older than STALE (HUNG for appliers); at most once per 10 min per container, audited.
    Returns {role: "ok" | "restarted: why"}. O(heartbeats + containers)."""
    import urllib.parse
    now = now or time.time()
    newest = {}
    for n in _count(FLEET):
        try:
            m = json.load(open(os.path.join(FLEET, n), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        key = m.get("role") if m.get("role") in WATCHED else (m.get("role"), m.get("host"))
        if m.get("role") in WATCHED or m.get("role") == "applier":
            if key not in newest or m.get("ts", 0) > newest[key].get("ts", 0):
                newest[key] = m
    out = {}
    for key, m in newest.items():
        role = key if isinstance(key, str) else key[0]
        age = now - m.get("ts", 0)
        if age <= HUNG.get(role, STALE.get(role, 120)):
            out[role] = out.get(role) or "ok"
            continue
        if role == "applier":  # the container's hostname is its short id; gone containers are the scaler's business
            rows = [r for r in (_docker("GET", "/containers/json") or []) if r.get("Id", "").startswith(m.get("host", "?"))]
        else:
            flt = urllib.parse.quote(json.dumps({"label": [f"com.docker.compose.service={role}"]}))
            rows = _docker("GET", f"/containers/json?filters={flt}") or []
        for r in rows[:1]:
            if r.get("State") != "running" or now - _restarted.get(r["Id"], 0) < 600:
                continue
            if role == "applier" and os.path.exists(drain_path(m.get("host", ""))):
                continue  # being drained by the scaler: not hung, on its way out
            _docker("POST", f"/containers/{r['Id']}/restart?t=10")
            _restarted[r["Id"]] = now
            audit("restart", role, reason=f"no heartbeat for {round(age)} s (last: {str(m.get('state'))[:60]})")
            out[role] = f"restarted: silent {round(age)} s"
    return out


DAILY_HOUR = int(os.environ.get("REGEN_DAILY_HOUR", "7"))  # local time; the container runs TZ=America/Los_Angeles
OUTREACH_PER_DAY = int(os.environ.get("REGEN_OUTREACH_PER_DAY", "20"))


def daily(imap, now=None, run=None):
    """Once a day after DAILY_HOUR: refresh HN "Who is hiring" boards + contacts, then save Gmail drafts for at most
    OUTREACH_PER_DAY contacts that never got one (nothing is sent; the user reviews Drafts). Runs in a thread so
    scaling never waits on it; skipped while killed. Returns True when it started today's run."""
    import subprocess, sys, threading
    now = now or time.localtime()
    mark = os.path.join(FLEET, "daily_last")
    today = time.strftime("%Y-%m-%d", now)
    try:
        last = open(mark, encoding="utf-8").read().strip()
    except OSError:
        last = ""
    if now.tm_hour < DAILY_HOUR or last == today or os.path.exists(os.path.join(WORKSPACE, "KILL")):
        return False
    os.makedirs(FLEET, exist_ok=True)
    open(mark, "w", encoding="utf-8").write(today)
    steps = [["hn", "2"]] + ([["outreach", "hn", str(OUTREACH_PER_DAY), "--gmail", "--new"]] if imap else [])

    def go():
        for s in steps:
            r = (run or subprocess.run)([sys.executable, "-m", "engine", *s], capture_output=True, text=True,
                                        encoding="utf-8", errors="replace", timeout=1800, preexec_fn=_as_engine_user)
            tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
            audit("daily", " ".join(s), rc=r.returncode, result=tail[0][:160])
    threading.Thread(target=go, daemon=True).start()
    return True


BENCH_HOURS = int(os.environ.get("REGEN_BENCH_HOURS", "6"))


# ---------------- evaluation containers ----------------
# Benchmarks B1-B10 (engine/bench.py) run in one-shot `eval` containers, never inside the supervisor: 0 of them most
# of the time, one per pending trigger up to MAX_EVALS. Triggers: a commit reposync pushed that was not evaluated
# yet, the last run being older than BENCH_HOURS, or workspace/bench/REQUEST (`supervise --eval`). Each container is
# built from the api container's config (engine image, bank volumes, the Postgres secret, the compose network),
# bounded like everything the supervisor creates, reaped and audited with its exit code when it ends.
MAX_EVALS = int(os.environ.get("REGEN_MAX_EVALS", "2"))
EVAL_GAP = 30 * 60  # the same trigger never launches twice within this (a failing run must not loop)


def _project_rows(service):
    import urllib.parse
    proj = os.environ.get("REGEN_COMPOSE_PROJECT", "deploy")
    flt = urllib.parse.quote(json.dumps({"label": [f"com.docker.compose.project={proj}",
                                                   f"com.docker.compose.service={service}"]}))
    return _docker("GET", f"/containers/json?all=1&filters={flt}") or []


def _bench_dir():
    return os.path.join(WORKSPACE, "bench")


def _own(path):
    """The supervisor runs as root; anything it creates in the bank must stay writable by the engine user (10001),
    or the eval container cannot save its results there (the 10-13 EACCES lesson)."""
    if os.name != "nt" and os.getuid() == 0:
        try:
            os.chown(path, 10001, 10001)
        except OSError:
            pass


def eval_triggers(now=None):
    """[(reason, sha)] pending right now, most specific first. O(events) via the cached ledger reader."""
    now = now or time.time()
    d = _bench_dir()
    out = []
    if os.path.exists(os.path.join(d, "REQUEST")):
        out.append(("manual", None))
    try:
        from engine.feedback.events import read
        pushed = [e for e in read("reposync") if e.get("action") == "code_pushed" and e.get("sha")]
    except Exception:
        pushed = []
    if pushed:
        try:
            last = open(os.path.join(d, "last_sha"), encoding="utf-8").read().strip()
        except OSError:
            last = ""
        if pushed[-1]["sha"] != last:
            out.append(("commit", pushed[-1]["sha"]))
    try:
        ts = json.load(open(os.path.join(d, "latest.json"), encoding="utf-8")).get("ts") or 0
    except (OSError, ValueError):
        ts = 0
    if now - ts > BENCH_HOURS * 3600:
        out.append(("schedule", None))
    return out


def launch_eval(reason, sha, existing):
    """Create + start one eval container from the api container's config. Returns its name. Raises Refused."""
    tmpl = next((r for r in _project_rows("api") if r.get("State") == "running"), None)
    if not tmpl:
        raise Refused("no running api container to take the eval config from")
    i = _docker("GET", f"/containers/{tmpl['Id']}/json") or {}
    proj = os.environ.get("REGEN_COMPOSE_PROJECT", "deploy")
    n = int(time.time()) % 100000
    name = f"{proj}-eval-{n}"
    labels = {"com.docker.compose.project": proj, "com.docker.compose.service": "eval",
              "regen.eval-reason": reason, "regen.eval-sha": sha or ""}
    hc = {k: i["HostConfig"].get(k) for k in ("Binds", "Mounts", "NetworkMode", "SecurityOpt", "CapDrop")
          if i["HostConfig"].get(k) is not None}
    nets = {k: {} for k in (i["NetworkSettings"].get("Networks") or {})}
    cmd = ["bench", "--save", "--reason", reason] + (["--sha", sha] if sha else [])
    env = [e for e in (i["Config"].get("Env") or []) if not e.startswith("REGEN_API_")] + ["REGEN_API_URL=http://api:8787"]
    body = bound({"Image": i["Config"]["Image"], "Env": env, "Entrypoint": ["python", "-m", "engine"], "Cmd": cmd,
                  "User": i["Config"].get("User"), "Labels": labels, "HostConfig": hc,
                  "NetworkingConfig": {"EndpointsConfig": nets}}, existing)
    new = _docker("POST", f"/containers/create?name={name}", body) or {}
    if not new.get("Id"):
        raise Refused(f"docker create failed: {str(new)[:80]}")
    _docker("POST", f"/containers/{new['Id']}/start")
    return name


def evals(now=None, _last={}):  # _last: when each trigger last launched (kept across calls)
    """Reap finished eval containers (audit exit code, delete), then launch one per pending trigger up to MAX_EVALS.
    Returns (launched, running). O(eval containers)."""
    now = now or time.time()
    rows = _project_rows("eval")
    running = []
    for r in rows:
        name = (r.get("Names") or ["/?"])[0].lstrip("/")
        if r.get("State") in ("exited", "dead"):
            st = (_docker("GET", f"/containers/{r['Id']}/json") or {}).get("State") or {}
            audit("eval_done", name, rc=st.get("ExitCode"), reason=(r.get("Labels") or {}).get("regen.eval-reason"))
            _docker("DELETE", f"/containers/{r['Id']}")
        elif r.get("State") != "created" or now - (r.get("Created") or now) < 600:
            running.append((r.get("Labels") or {}).get("regen.eval-reason"))
        else:  # created but never started for 10 min: remove it
            _docker("DELETE", f"/containers/{r['Id']}?force=1")
    launched = []
    for reason, sha in eval_triggers(now):
        if len(running) >= MAX_EVALS:
            break
        if reason in running or reason in _last and now - _last[reason] < EVAL_GAP:
            continue
        _last[reason] = now
        try:
            name = launch_eval(reason, sha, len(running))
        except Refused as ex:
            audit("refuse", "create eval", reason=str(ex)[:120], trigger=reason)
            continue
        d = _bench_dir()
        os.makedirs(d, exist_ok=True)
        _own(d)
        if reason == "manual":
            try:
                os.remove(os.path.join(d, "REQUEST"))
            except OSError:
                pass
        if sha:
            open(os.path.join(d, "last_sha"), "w", encoding="utf-8").write(sha)
            _own(os.path.join(d, "last_sha"))
        audit("eval", name, trigger=reason, sha=sha)
        running.append(reason)
        launched.append(name)
        break  # one per pass: a commit run also refreshes latest.json, which settles the schedule trigger
    return launched, len(running)


def bench():
    """Benchmarks in a subprocess (engine/bench.py --save -> workspace/bench/latest.json); audited. Fallback for a
    stack without the eval path (no api container); evals() is the normal route."""
    import subprocess, sys
    t = time.time()
    r = subprocess.run([sys.executable, "-m", "engine", "bench", "--save"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    audit("bench", "B1-B7", rc=r.returncode, seconds=round(time.time() - t))


def _as_engine_user():
    """preexec_fn for subprocesses that write the bank: the supervisor runs as root (Docker socket), the bank's files
    belong to the engine user (uid 10001); a root-owned queue.json made the pipeline fail with EACCES (10-13)."""
    if os.name != "nt" and os.getuid() == 0:
        os.setgid(10001); os.setuid(10001)


def alerts():
    """`engine alerts --imap 2` as the engine user (only the supervisor has the Gmail app password); audited."""
    import subprocess, sys
    r = subprocess.run([sys.executable, "-m", "engine", "alerts", "--imap", "2"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800, preexec_fn=_as_engine_user,
                       env=dict(os.environ, HOME="/home/regen"))
    tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
    audit("alerts", "imap", rc=r.returncode, result=tail[0][:160])


def supervise(argv=None):
    """The container on top: every 15 s scale appliers to the backlog and requeue lost claims; if a Gmail app
    password is configured, watch IMAP for codes in a thread (hands-free, no browser tab)."""
    import threading
    out = control(argv)
    if out is not None:
        print(json.dumps(out, default=str))
        return
    lo = int(os.environ.get("REGEN_MIN_APPLIERS", "1"))
    hi = int(os.environ.get("REGEN_MAX_APPLIERS", "7"))
    from engine.notify import _env
    e = _env()
    imap = bool(e.get("REGEN_SMTP_USER") and e.get("REGEN_SMTP_APP_PASSWORD"))
    if imap:
        from engine.apply.codes import watch
        def codes_forever():  # reconnect after a dropped IMAP connection; say why it failed instead of dying silently
            while True:
                try:
                    watch()
                except BaseException as ex:  # SystemExit too: watch() raises it on bad credentials
                    print(f"supervisor: IMAP watcher stopped: {str(ex)[:120]}; retry in 60 s", flush=True)
                    beat("codes", state=f"error: {str(ex)[:80]}")
                time.sleep(60)
        threading.Thread(target=codes_forever, daemon=True).start()
        print("supervisor: IMAP code watcher on", flush=True)
    print(f"supervisor: appliers {lo}..{hi}", flush=True)
    n, svc = 0, {}
    while True:
        try:
            if os.path.exists(os.path.join(WORKSPACE, "KILL")):
                beat("supervisor", state="KILLED: " + open(os.path.join(WORKSPACE, "KILL")).read().strip()[:100])
                time.sleep(15)
                continue
            guard()
            want, running, jobs = scale(*limits(lo, hi))
            if n % 8 == 0:
                requeue_stale()
            daily(imap)
            if n % 240 == 0:  # hourly: dangling images, then the retention policy (engine/clean.py)
                prune_images()
                from engine.clean import main as clean
                clean([])
            if n >= 8:  # from 2 min after start: oil-life inspection every 5 min, the oil change when due (v1.2)
                from engine.oilchange import tick_async
                tick_async()
            if imap and n % 240 == 40:  # hourly (10 min after start): LinkedIn alert mail -> leads -> queue
                threading.Thread(target=alerts, daemon=True).start()
            if n % 4 == 2 and n >= 20:  # every minute from 5 min after start: eval containers for pending triggers
                evals()
            if n % 4 == 0:  # every minute
                enforce()
                svc = services()
                live = liveness()  # running but silent -> restarted (audited)
                svc.update({k: v for k, v in live.items() if v != "ok"})
                threading.Thread(target=inventory, daemon=True).start()  # stats take ~1 s each: off the 15 s loop
            beat("supervisor", state="supervising", want=want, running=running, jobs=jobs, imap=imap, services=svc)
        except Exception as ex:  # never die: a supervisor that crashes leaves the fleet at its last size
            print(f"supervisor: {ex}", flush=True)
            beat("supervisor", state=f"error: {str(ex)[:80]}")
        n += 1
        time.sleep(15)


def main(argv=None):
    if "--json" in (argv or []):
        print(json.dumps(status(), default=str))
        return
    f = fleet()
    print(f"fleet: {f['verdict']} | inbox {f['inbox']}, claimed {f['claimed']}, done {f['done']}, "
          f"codes waiting {len(f['codes_waiting'])}, Gmail tab last post "
          + (f"{f['gmail_tab_age']}s ago" if f["gmail_tab_age"] is not None else "never"))
    for m in f["members"]:
        extra = " ".join(f"{k}={m[k]}" for k in ("state", "batch", "pass", "codes") if m.get(k) not in (None, ""))
        print(f"  {'up  ' if m['up'] else 'DOWN'} {m['role']:<8} {m['host']:<14} {m['age']:>5}s ago  {extra}")
    for p in f["problems"]:
        print(f"  ! {p}")


if __name__ == "__main__":
    main()
