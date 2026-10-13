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
STALE = {"applier": 120, "relay": 120, "pipeline": 30 * 60}  # pipeline sleeps between passes; it beats on wake-up
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
        for r in drains[:need]:  # cancel a drain before adding a container
            os.remove(drain_path(r[0][:12]))
            drains.remove(r)
            need -= 1
        stopped = [r for r in rows if not r[2]]
        for cid, name, _ in stopped[:need]:
            _docker("POST", f"/containers/{cid}/start")
            audit("start", name, jobs=jobs, want=want)
        for _ in range(max(0, need - len(stopped))):  # none left to start: create one
            if running:
                audit("create", clone(running[0][0], appliers()), jobs=jobs, want=want)
    elif len(active) > want:
        for cid, name, up in reversed(active[:]):
            if len(active) <= want:
                break
            m = beats.get(cid[:12])
            if m and m["up"] and m.get("state") == "watching":
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


def clone(cid, rows):
    """Create and start a new applier from a running one's config (same image, env, volumes, limits, compose labels).
    Returns the new container's name. O(1) API calls."""
    i = _docker("GET", f"/containers/{cid}/json")
    used = {int(n.rsplit("-", 1)[1]) for _, n, _ in rows if n.rsplit("-", 1)[-1].isdigit()}
    n = next(k for k in range(1, 100) if k not in used)
    name = re.sub(r"-\d+$", f"-{n}", i["Name"].lstrip("/"))
    labels = dict(i["Config"].get("Labels") or {}, **{"com.docker.compose.container-number": str(n)})
    hc = {k: i["HostConfig"].get(k) for k in ("Binds", "Mounts", "ShmSize", "NanoCpus", "Memory", "RestartPolicy",
                                              "NetworkMode", "SecurityOpt", "CapDrop", "ReadonlyRootfs")
          if i["HostConfig"].get(k) is not None}
    nets = {k: {"Aliases": [f"applier-{n}"]} for k in (i["NetworkSettings"].get("Networks") or {})}
    body = {"Image": i["Config"]["Image"], "Env": i["Config"].get("Env"), "Entrypoint": i["Config"].get("Entrypoint"),
            "Cmd": i["Config"].get("Cmd"), "User": i["Config"].get("User"), "Labels": labels, "HostConfig": hc,
            "NetworkingConfig": {"EndpointsConfig": nets}}
    new = _docker("POST", f"/containers/create?name={name}", body) or {}
    if new.get("Id"):
        _docker("POST", f"/containers/{new['Id']}/start")
    return name


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


def kill(reason):
    """The kill switch: workers stop after their current step (batches/STOP), appliers and the pipeline are stopped
    now, the supervisor holds (KILL) and the reason is recorded. After investigating:
    docker exec deploy-supervisor-1 python -m engine supervise --clear"""
    import urllib.parse
    for n in (os.path.join("batches", "STOP"), "KILL"):
        p = os.path.join(WORKSPACE, n)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {reason}\n")
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
    """(min, max) appliers: the env defaults, unless `supervise --scale` wrote an override (kept across restarts)."""
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
    if "--quarantine" in a:
        return {"quarantine": quarantine_list()}
    return None


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
                                        encoding="utf-8", errors="replace", timeout=1800)
            tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
            audit("daily", " ".join(s), rc=r.returncode, result=tail[0][:160])
    threading.Thread(target=go, daemon=True).start()
    return True


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
    n = 0
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
            beat("supervisor", state="supervising", want=want, running=running, jobs=jobs, imap=imap)
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
