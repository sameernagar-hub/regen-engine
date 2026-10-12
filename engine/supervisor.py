"""Fleet supervisor: every container writes a small heartbeat into the shared workspace, and fleet() reads them back
with the batch queue, so the control room can show container health without the Docker socket (mounting it would
hand every container root on the host).

  workspace/fleet/<role>_<host>.json   {"role", "host", "ts", "state", ...}   (atomic replace, one file per process)

Roles: pipeline (pass number, next scan), applier (watching / applying <batch>), relay (last POST from the Gmail tab,
codes written). A heartbeat older than STALE seconds reads as "down".

    python -m engine fleet        prints the same summary as GET /api/control/fleet
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
