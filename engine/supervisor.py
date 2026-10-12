"""Fleet supervisor: every container writes a small heartbeat into the shared workspace, and fleet() reads them back
with the batch queue, so the control room can show container health without the Docker socket (mounting it would
hand every container root on the host).

  workspace/fleet/<role>_<host>.json   {"role", "host", "ts", "state", ...}   (atomic replace, one file per process)

Roles: pipeline (pass number, next scan), applier (watching / applying <batch>), relay (last POST from the Gmail tab,
codes written). A heartbeat older than STALE seconds reads as "down".

    python -m engine fleet        prints the same summary as GET /api/control/fleet
    python -m engine supervise    the supervisor container: autoscale appliers, requeue lost claims, IMAP codes

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
    if tab_age is None or tab_age > 120:
        problems.append("Gmail tab is not posting codes (re-paste gmail_relay.js; keep the tab active)")
    if stale:
        problems.append(f"{len(stale)} claimed batch(es) lost with their container: python scripts/requeue.py --stale")
    return {"members": members, "inbox": len(_count(os.path.join(BOX, "inbox"))), "claimed": len(claimed),
            "done": len(_count(os.path.join(BOX, "done"))), "stale_claims": stale, "codes_waiting": waiting,
            "gmail_tab_age": round(tab_age) if tab_age is not None else None, "problems": problems,
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


def scale(lo, hi, idle_grace=180, _idle={}):  # _idle: first time each container was seen idle (kept across calls)
    """Start stopped appliers up to desired(); stop idle ones above it (idle for idle_grace s). O(containers)."""
    want, jobs = desired(lo, hi)
    rows = appliers()
    running = [r for r in rows if r[2]]
    beats = {m["host"]: m for m in fleet()["members"] if m.get("role") == "applier"}
    now = time.time()
    if len(running) < want:
        stopped = [r for r in rows if not r[2]]
        for cid, name, _ in stopped[: want - len(running)]:
            _docker("POST", f"/containers/{cid}/start")
            audit("start", name, jobs=jobs, want=want)
        for _ in range(max(0, want - len(running) - len(stopped))):  # none left to start: create one
            if running:
                audit("create", clone(running[0][0], appliers()), jobs=jobs, want=want)
    elif len(running) > want:
        for cid, name, _ in reversed(running):
            if len(running) <= want:
                break
            m = beats.get(cid[:12])  # a container's hostname is its short id
            if m and m["up"] and m.get("state") == "watching":
                first = _idle.setdefault(cid, now)
                if now - first >= idle_grace:
                    _docker("POST", f"/containers/{cid}/stop?t=20")
                    _docker("DELETE", f"/containers/{cid}")  # idle capacity is removed, not parked
                    running = [r for r in running if r[0] != cid]
                    _idle.pop(cid, None)
                    audit("remove", name, jobs=jobs, want=want)
            else:
                _idle.pop(cid, None)
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
SECRET_RX = [
    re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|xox[abp]-[A-Za-z0-9-]{20,}|AIza[0-9A-Za-z_-]{30,})"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN shape
]
_scanned = {}


def _secrets():
    """Exact secret values from the environment (.env): the app password, tokens. Never logged themselves."""
    from engine.notify import _env
    e = _env()
    return [(k, v.replace(" ", "")) for k, v in e.items()
            if re.search(r"PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE", k) and len((v or "").replace(" ", "")) >= 8]


def guard():
    """Scan files written since the last pass (logs, outreach, finished batches, top-level ledger files) for secret
    values from .env and secret shapes. A hit is a kill: kill() + the file moved to quarantine/ (kept for review,
    never deleted automatically) + an audit record naming the file and rule (never the secret). O(new bytes)."""
    import shutil
    secrets = _secrets()
    hits = []
    for sub in ("logs", "outreach", os.path.join("batches", "done"), ""):
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
            flat = text.replace(" ", "")
            rule = next((k for k, v in secrets if v in flat), None) or \
                next((f"pattern {i}" for i, rx in enumerate(SECRET_RX) if rx.search(text)), None)
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


def supervise(argv=None):
    """The container on top: every 15 s scale appliers to the backlog and requeue lost claims; if a Gmail app
    password is configured, watch IMAP for codes in a thread (hands-free, no browser tab)."""
    import threading
    lo = int(os.environ.get("REGEN_MIN_APPLIERS", "1"))
    hi = int(os.environ.get("REGEN_MAX_APPLIERS", "7"))
    from engine.notify import _env
    e = _env()
    if e.get("REGEN_SMTP_USER") and e.get("REGEN_SMTP_APP_PASSWORD"):
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
    if "--clear" in (argv or []):  # after investigating a kill
        for x in (os.path.join("batches", "STOP"), "KILL"):
            if os.path.exists(os.path.join(WORKSPACE, x)):
                os.remove(os.path.join(WORKSPACE, x))
        audit("clear", "kill switch")
        return
    while True:
        try:
            if os.path.exists(os.path.join(WORKSPACE, "KILL")):
                beat("supervisor", state="KILLED: " + open(os.path.join(WORKSPACE, "KILL")).read().strip()[:100])
                time.sleep(15)
                continue
            guard()
            want, running, jobs = scale(lo, hi)
            if n % 8 == 0:
                requeue_stale()
            if n % 240 == 0:
                prune_images()
            beat("supervisor", state="supervising", want=want, running=running, jobs=jobs)
        except Exception as ex:  # never die: a supervisor that crashes leaves the fleet at its last size
            print(f"supervisor: {ex}", flush=True)
            beat("supervisor", state=f"error: {str(ex)[:80]}")
        n += 1
        time.sleep(15)


def main(argv=None):
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
