"""`python -m engine scan [days] [--ats greenhouse,ashby,lever] [--hot]`

Scan every registered board (workspace/boards.json), keep jobs first published in the last `days`
that pass the domain filter (engine/discovery/filters.py), drop anything already applied to,
and write workspace/queue.json, newest first.

Board ranking: every scan records each board's postings from the last 7 days in workspace/board_activity.json
({"ats:token": {"week": n, "seen": iso}}). `--hot` (the pipeline's short loop passes) fetches only boards that
posted in the last week plus any not fetched for COLD_HOURS, so quiet boards are still checked daily.
"""
import json, os, sys, time
from datetime import datetime, timezone, timedelta

from engine.config import WORKSPACE
from engine.discovery import ats as A
from engine.discovery.filters import load_domain, keep, applied_keys, norm


def filter_jobs(jobs, days, dom=None, source="ats"):
    dom = dom or load_domain()
    ids, keys = applied_keys()
    cut = datetime.now(timezone.utc) - timedelta(days=days)
    out, seen, dropped = [], set(), {}
    for j in jobs:
        if not j.get("posted") or datetime.fromisoformat(j["posted"]) < cut:
            continue
        why = keep(dom, j["title"], j["location"], j["company"])
        if not why and (j["id"] in ids or norm(f"{j['company']} - {j['title']}") in keys):
            why = "already applied"
        k = (j["ats"], j["id"])
        if not why and k in seen:
            why = "duplicate"
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        seen.add(k)
        out.append({"source": j.get("source", source), **j})
    out.sort(key=lambda r: r["posted"], reverse=True)
    return out, dropped


def merge_queue(new, path=None, log=True):
    """Merge into queue.json without losing jobs found earlier by another source. Each job not queued before is
    recorded as `discovered` (the Discover station; 10-18: the loop's scans logged none, so it read 0 today)
    unless the caller records its own (`log=False`: watch, alerts)."""
    path = path or os.path.join(WORKSPACE, "queue.json")
    old = json.load(open(path)) if os.path.exists(path) else []
    by = {str(j["id"]): j for j in old if j.get("ats")}  # legacy greenhouse-only records lack "ats"
    fresh = [j for j in new if str(j["id"]) not in by]
    for j in new:
        by[str(j["id"])] = j
    if log and fresh:
        from engine.feedback.events import record
        for j in fresh:
            record("discovered", job=f"{j['company']} - {j['title']}", url=j.get("url"), ats=j.get("ats"),
                   source=j.get("source", "ats"))
    keep_after = (datetime.now(timezone.utc) - timedelta(days=21)).isoformat()  # bound the queue: 3 weeks of postings
    q = sorted((j for j in by.values() if (j.get("posted") or keep_after) >= keep_after),
               key=lambda r: r.get("posted") or "", reverse=True)
    json.dump(q, open(path, "w"), indent=1)
    return q


COLD_HOURS = 24
ACTIVITY = os.path.join(WORKSPACE, "board_activity.json")


def load_activity():
    try:
        return json.load(open(ACTIVITY, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def hot_boards(boards, activity, now=None):
    """"ats:token" boards worth fetching on a short pass: posted in the last week, or not fetched for COLD_HOURS
    (never-fetched boards count as due). O(boards)."""
    now = now or datetime.now(timezone.utc)
    due = (now - timedelta(hours=COLD_HOURS)).isoformat()
    out = set()
    for a in A.ATS:
        for t in boards.get(a, []):
            k = f"{a}:{t}"
            st = activity.get(k)
            if not st or st.get("week", 0) > 0 or (st.get("seen") or "") < due:
                out.add(k)
    return out


def scan(days=3, only=None, hot=False):
    t0 = time.time()
    boards = A.load_boards()
    if only:
        boards = {a: (boards[a] if a in only else []) for a in A.ATS}
    cut = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    activity, counts = load_activity(), {}
    subset = hot_boards(boards, activity) if hot else None
    jobs, dead, total = A.fetch_all(boards, keep=lambda j: (j.get("posted") or "") >= cut,  # stream: hold only fresh postings
                                    activity=counts, only=subset)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    activity.update({k: {"week": n, "seen": stamp} for k, n in counts.items()})
    tmp = ACTIVITY + ".tmp"
    json.dump(activity, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, ACTIVITY)
    out, dropped = filter_jobs(jobs, days)
    os.makedirs(WORKSPACE, exist_ok=True)
    out = merge_queue(out)  # 10-10: a short rescan used to overwrite the queue and drop 70 untried jobs
    if dead:
        b = A.load_boards()
        b["dead"] = sorted(set(b.get("dead", [])) | {f"{a}:{t}" for a, t in dead})
        A.save_boards(b)
    n = len(subset) if subset is not None else sum(len(v) for k, v in boards.items() if k in A.ATS)
    print(f"scanned {n} boards{' (hot)' if hot else ''}, {total} postings ({len(jobs)} fresh) in {time.time() - t0:.0f}s; dropped {dropped}; {len(dead)} dead boards")
    return out


def show(out):
    for r in out:
        print(f"{r['id']} | {r['posted'][5:16].replace('T', ' ')} | {r['ats'][:2]} | {r['company'][:22]} | {r['title'][:60]} | {r['location'][:35]}")
    print(len(out), "jobs -> workspace/queue.json")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    only = None
    if "--ats" in argv:
        i = argv.index("--ats"); only = argv[i + 1].split(","); argv = argv[:i] + argv[i + 2:]
    hot = "--hot" in argv
    argv = [a for a in argv if a != "--hot"]
    show(scan(float(argv[0]) if argv else 3, only, hot))


if __name__ == "__main__":
    main()
