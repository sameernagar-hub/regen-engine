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
import json, os, socket, time

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


def _docker(method, path):
    """One Docker Engine API call over the unix socket (stdlib only). Returns parsed JSON or None."""
    import http.client, socket as so
    class C(http.client.HTTPConnection):
        def connect(self):
            self.sock = so.socket(so.AF_UNIX, so.SOCK_STREAM); self.sock.connect(SOCK)
    c = C("docker", timeout=30)
    c.request(method, path)
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
        for cid, name, _ in [r for r in rows if not r[2]][: want - len(running)]:
            _docker("POST", f"/containers/{cid}/start")
            print(f"scale: start {name} ({jobs} jobs waiting, want {want})", flush=True)
    elif len(running) > want:
        for cid, name, _ in reversed(running):
            if len(running) <= want:
                break
            m = beats.get(cid[:12])  # a container's hostname is its short id
            if m and m["up"] and m.get("state") == "watching":
                first = _idle.setdefault(cid, now)
                if now - first >= idle_grace:
                    _docker("POST", f"/containers/{cid}/stop?t=20")
                    running = [r for r in running if r[0] != cid]
                    _idle.pop(cid, None)
                    print(f"scale: stop {name} (idle; {jobs} jobs waiting, want {want})", flush=True)
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
    for n in f["stale_claims"]:
        src = os.path.join(DIRS["claimed"], n)
        try:
            jobs = [j for j in json.load(open(src, encoding="utf-8")) if st.get(j["url"]) not in ("SUBMITTED", "SKIPPED")]
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
        threading.Thread(target=watch, daemon=True).start()
        print("supervisor: IMAP code watcher on", flush=True)
    print(f"supervisor: appliers {lo}..{hi}", flush=True)
    n = 0
    while True:
        try:
            want, running, jobs = scale(lo, hi)
            if n % 8 == 0:
                requeue_stale()
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
