"""Requeue jobs from batch files after a fix: keeps only jobs that are not final (SUBMITTED / SKIPPED) and whose
company is not waiting on the user, drops duplicates, and writes one batch into batches/inbox for the workers.
Stale claims (a worker died mid-batch) are moved to batches/stale/ first, never deleted.

  python scripts/requeue.py batches/run_X.json [...] [--stale]     (run inside the pipeline container)
O(E + J)."""
import glob, json, os, shutil, sys, time

from engine.config import WORKSPACE
from engine.apply.worker import DIRS
from engine.pipeline import history, in_flight, latest_status, split


def main(args):
    os.chdir(WORKSPACE)
    files = [a for a in args if not a.startswith("--")]
    if "--stale" in args:  # a claim older than 30 min with no live worker on it
        os.makedirs("batches/stale", exist_ok=True)
        for f in glob.glob(os.path.join(DIRS["claimed"], "*.json")):
            if time.time() - os.path.getmtime(f) > 1800:
                dst = os.path.join("batches/stale", os.path.basename(f))
                shutil.move(f, dst); files.append(dst)
                if os.path.exists(f + ".lock"): shutil.move(f + ".lock", dst + ".lock")
    st, (_, blocked) = latest_status(), history()
    out, seen, busy = [], set(), in_flight()
    from engine.feedback.events import read
    done = {(e.get("job") or "").lower().strip() for e in read("application")  # same role under another URL
            if not e.get("dry") and (e.get("status") or "").startswith("SUBMITTED")}
    for f in files:
        for j in json.load(open(f, encoding="utf-8")):
            co = j["name"].split(" - ")[0].lower()
            key = j["name"].lower().strip()
            if j["url"] in seen or key in seen or key in done or key in busy or st.get(j["url"]) in ("SUBMITTED", "SKIPPED", "NEEDS YOU") or co in blocked:
                continue
            seen |= {j["url"], key}; out.append(j)
    stamp = time.strftime('%H%M')
    for i, part in enumerate(split(out, int(os.environ.get("REGEN_PARTS", "5")))):  # one file per applier
        name = f"requeue_{stamp}_{i}.json"
        tmp = os.path.join(DIRS["inbox"], "." + name)
        json.dump(part, open(tmp, "w", encoding="utf-8"), indent=1)
        os.replace(tmp, os.path.join(DIRS["inbox"], name))
        print(f"requeue: {len(part)} jobs -> batches/inbox/{name}")

if __name__ == "__main__":
    main(sys.argv[1:])
