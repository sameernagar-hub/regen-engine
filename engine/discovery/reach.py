"""Reach list: jobs on ATSs the engine discovers but does not submit to (ats.REACH: Workday, iCIMS, SmartRecruiters).

    python -m engine reach [max=12]

Workday and iCIMS put the application behind a candidate account (sign-in, often email verification), which is the
user's to create; SmartRecruiters has no filler yet. So for these the engine does everything up to the click: the
same title filter, fit gate and trust gate as every other job (batch.build), a tailored resume, and one row in
workspace/reach.json + reach.md (link, posted, lane, JD coverage, resume path). The pipeline runs this after each
scan (REGEN_REACH_PER_PASS per pass, newest first) and select() leaves these ATSs out of apply batches.

Already-listed jobs are skipped (reach.json holds every row ever listed; `seen` is its URL set), so a pass costs one
JD fetch per new job. O(queue) to pick, O(rows) to rewrite the list.
"""
import datetime, json, os, sys

from engine.config import WORKSPACE
from engine.discovery.ats import REACH

PATH = os.path.join(WORKSPACE, "reach.json")
PER_PASS = int(os.environ.get("REGEN_REACH_PER_PASS", "12"))


def load():
    try:
        return json.load(open(PATH, encoding="utf-8"))
    except (OSError, ValueError):
        return []


def pick(queue, rows, limit):
    """Newest REACH jobs in the queue that were never listed (or skipped). O(Q log Q)."""
    seen = {r["url"] for r in rows}
    todo = [j for j in queue if j.get("ats") in REACH and j.get("url") not in seen]
    todo.sort(key=lambda j: j.get("posted") or "", reverse=True)
    return todo[:limit]


def write(rows):
    tmp = PATH + ".tmp"
    json.dump(rows, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, PATH)
    live = [r for r in rows if r.get("resume")]
    md = ["# Reach list: resume ready, you submit (Workday / iCIMS need your candidate account)", "",
          "| Listed | ATS | Company | Role | Location | Lane | JD match | Resume |", "|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['listed'][:16]} | {r['ats']} | {r['company']} | [{r['title']}]({r['url']}) | {r.get('location', '')[:40]} | "
           f"{r.get('lane', '')} | {r.get('jd_match', '')} | `{r['resume']}` |" for r in reversed(live)]
    open(os.path.join(WORKSPACE, "reach.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")


def run(queue=None, limit=PER_PASS):
    """Build resumes for up to `limit` new reach jobs and add them to the list. Returns the new rows."""
    if queue is None:
        try:
            queue = json.load(open(os.path.join(WORKSPACE, "queue.json"), encoding="utf-8"))
        except (OSError, ValueError):
            queue = []
    rows = load()
    todo = pick(queue, rows, limit)
    if not todo:
        return []
    from engine.tailoring.batch import build
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    built = {b["url"]: b for b in build(f"reach_{stamp}", [str(j["id"]) for j in todo])}
    now = datetime.datetime.now().isoformat(timespec="seconds")
    new = []
    for j in todo:
        b = built.get(j["url"])
        if b:
            new.append({"listed": now, "ats": j["ats"], "company": j["company"], "title": j["title"], "url": j["url"],
                        "location": j.get("location", ""), "posted": j.get("posted"), "lane": b.get("lane"),
                        "jd_match": b.get("jd_match"), "resume": b["resume"], "salary_range": b.get("salary_range")})
        else:  # fit gate / trust gate / posting gone: remembered so it is not fetched again
            rows.append({"listed": now, "ats": j["ats"], "company": j["company"], "title": j["title"],
                         "url": j["url"], "skipped": True})
    write(rows + new)
    print(f"reach: {len(new)} of {len(todo)} new jobs listed with a resume -> workspace/reach.md")
    return new


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    run(limit=int(argv[0]) if argv else PER_PASS)


if __name__ == "__main__":
    main()
