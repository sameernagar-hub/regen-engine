"""`python -m engine scan [days] [--ats greenhouse,ashby,lever]`

Scan every registered board (workspace/boards.json), keep jobs first published in the last `days`
that pass the domain filter (engine/discovery/filters.py), drop anything already applied to,
and write workspace/queue.json, newest first.
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


def merge_queue(new, path=None):
    """Merge into queue.json without losing jobs found earlier by another source."""
    path = path or os.path.join(WORKSPACE, "queue.json")
    old = json.load(open(path)) if os.path.exists(path) else []
    by = {str(j["id"]): j for j in old if j.get("ats")}  # legacy greenhouse-only records lack "ats"
    for j in new:
        by[str(j["id"])] = j
    q = sorted(by.values(), key=lambda r: r.get("posted") or "", reverse=True)
    json.dump(q, open(path, "w"), indent=1)
    return q


def scan(days=3, only=None):
    t0 = time.time()
    boards = A.load_boards()
    if only:
        boards = {a: (boards[a] if a in only else []) for a in A.ATS}
    jobs, dead = A.fetch_all(boards)
    out, dropped = filter_jobs(jobs, days)
    os.makedirs(WORKSPACE, exist_ok=True)
    json.dump(out, open(os.path.join(WORKSPACE, "queue.json"), "w"), indent=1)
    if dead:
        b = A.load_boards()
        b["dead"] = sorted(set(b.get("dead", [])) | {f"{a}:{t}" for a, t in dead})
        A.save_boards(b)
    n = sum(len(v) for k, v in boards.items() if k in A.ATS)
    print(f"scanned {n} boards, {len(jobs)} postings in {time.time() - t0:.0f}s; dropped {dropped}; {len(dead)} dead boards")
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
    show(scan(float(argv[0]) if argv else 3, only))


if __name__ == "__main__":
    main()
