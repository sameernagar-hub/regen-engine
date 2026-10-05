"""`python -m engine watch [minutes=10] [--once]`: be first. Poll every registered board on a short
interval and surface only postings that did not exist on the previous poll.

  workspace/seen.json   every (ats:id) ever observed, so a restart never re-announces old jobs
  workspace/queue.json  new matches are merged in (ready for `batch`)
  workspace/new.jsonl   one line per new match (what a dashboard or agent tails)
  events.jsonl          kind=discovered, for the feedback loop (time-to-apply, source quality)
  REGEN_WEBHOOK         optional URL: each poll's new matches are POSTed as JSON (Slack/Discord/n8n/Zapier)

The first poll only seeds seen.json (nothing is announced), so the stream is truly "new since I started".
"""
import json, os, sys, time, urllib.request
from datetime import datetime, timezone

from engine.config import WORKSPACE
from engine.discovery import ats as A
from engine.discovery.scan import filter_jobs, merge_queue
from engine.feedback.events import record


def _post(url, payload):
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print("  ! webhook:", e)


def poll(seen):
    jobs, _ = A.fetch_all(A.load_boards())
    fresh = [j for j in jobs if f"{j['ats']}:{j['id']}" not in seen]
    first = not seen
    seen.update(f"{j['ats']}:{j['id']}" for j in jobs)
    if first:
        return [], len(jobs)
    # a posting new to us but published long ago is a board we just added; only keep the last 2 days
    matches, _ = filter_jobs(fresh, 2)
    return matches, len(jobs)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    once = "--once" in argv
    argv = [a for a in argv if a != "--once"]
    every = float(argv[0]) if argv else 10
    seen_p = os.path.join(WORKSPACE, "seen.json")
    seen = set(json.load(open(seen_p))) if os.path.exists(seen_p) else set()
    hook = os.environ.get("REGEN_WEBHOOK")
    while True:
        t0 = time.time()
        try:
            matches, n = poll(seen)
        except Exception as e:
            print("  ! poll failed:", e); matches, n = [], 0
        json.dump(sorted(seen), open(seen_p, "w"))
        now = datetime.now(timezone.utc)
        if matches:
            merge_queue(matches)
            with open(os.path.join(WORKSPACE, "new.jsonl"), "a", encoding="utf-8") as fh:
                for j in matches:
                    lag = (now - datetime.fromisoformat(j["posted"])).total_seconds() / 60
                    j["found_after_min"] = round(lag)
                    fh.write(json.dumps(j) + "\n")
                    record("discovered", job=f"{j['company']} - {j['title']}", url=j["url"], ats=j["ats"], lag_min=round(lag))
                    print(f"NEW {j['posted'][11:16]}Z (+{round(lag)}m) | {j['ats'][:2]} | {j['id']} | {j['company']} | {j['title']} | {j['location'][:30]}", flush=True)
            if hook:
                _post(hook, {"source": "regen-engine", "new_jobs": matches})
        print(f"[{datetime.now():%H:%M}] polled {n} postings in {time.time() - t0:.0f}s, {len(matches)} new matches", flush=True)
        if once:
            break
        time.sleep(max(30, every * 60 - (time.time() - t0)))


if __name__ == "__main__":
    main()
