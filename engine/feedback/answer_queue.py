"""The answer queue: answers typed on /needs reach the engine through one container, then the jobs go again.

    python -m engine answers [--watch]

  workspace/answers/inbox/<ts>_<id>.json     the API drops each answer here (validated first, atomic rename)
  workspace/answers/claimed/                 the `answers` container claims one by renaming it (exactly one owner)
  workspace/answers/done/ | refused/         after it is saved to profile/answers.json, or refused with a reason

One drain: claim every waiting answer, save each through answers.save (same refusals: legal, sponsorship, EEO and
sensitive questions come from presets only), find each job's batch entry wherever it is (batches/inbox, claimed,
done, stale, or a local batch file), drop ONE retry batch into batches/inbox (the supervisor scales appliers to it),
and record `answer_applied` / `answer_retry` events. Jobs already submitted are not retried. Holds while KILL is on.
O(answers + batch files).
"""
import datetime, glob, hashlib, json, os, sys, time

from engine.config import WORKSPACE
from engine.feedback import answers as A
from engine.feedback.events import record

QDIR = os.path.join(WORKSPACE, "answers")
BOX = os.path.join(WORKSPACE, "batches")


def _dirs():
    out = {k: os.path.join(QDIR, k) for k in ("inbox", "claimed", "done", "refused")}
    for d in out.values():
        os.makedirs(d, exist_ok=True)
    return out


def enqueue(job, question, answer):
    """Validate (same rules as save) and queue one answer. Returns the record the page shows; raises ValueError."""
    question, answer = A.validate(question, answer)
    d = _dirs()
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    name = f"{ts.replace(':', '')}_{hashlib.sha1(f'{job}|{question}'.encode()).hexdigest()[:8]}.json"
    tmp = os.path.join(d["inbox"], "." + name)
    json.dump({"job": job, "question": question, "answer": answer, "ts": ts}, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, os.path.join(d["inbox"], name))  # appears whole: the container never reads half a file
    record("answer_queued", job=job, question=question[:300])
    return {"pattern": A.pattern_for(question), "answer": answer, "source": f"queued {ts}, for {job}"}


def find_entry(job):
    """The newest batch entry for this job label, from any batch folder. None when the job was never batched."""
    files = []
    for sub in ("inbox", "claimed", "done", "stale", ""):
        files += [f for f in glob.glob(os.path.join(BOX, sub, "*.json")) if not os.path.basename(f).startswith(".")]
    for f in sorted(set(files), key=os.path.getmtime, reverse=True):
        try:
            hit = next((j for j in json.load(open(f, encoding="utf-8")) if isinstance(j, dict) and j.get("name") == job), None)
        except (OSError, ValueError, TypeError):
            continue
        if hit:
            return {k: v for k, v in hit.items() if not k.startswith("_")}
    return None


def drain():
    """Claim, save, retry. Returns {"saved", "refused", "retry"} counts."""
    d = _dirs()
    if os.path.exists(os.path.join(WORKSPACE, "KILL")):
        return {"held": True}
    saved, refused, jobs = 0, 0, []
    for n in sorted(os.listdir(d["inbox"])):
        if not n.endswith(".json") or n.startswith("."):
            continue
        mine = os.path.join(d["claimed"], n)
        try:
            os.replace(os.path.join(d["inbox"], n), mine)  # the claim
        except OSError:
            continue
        try:
            item = json.load(open(mine, encoding="utf-8"))
            A.save(item["job"], item["question"], item["answer"], requeue_job=False)
        except (ValueError, KeyError, OSError) as e:
            refused += 1
            record("answer_refused", job=str(locals().get("item", {}).get("job", "?")), reason=str(e)[:200])
            os.replace(mine, os.path.join(d["refused"], n))
            continue
        saved += 1
        record("answer_applied", job=item["job"], question=item["question"][:300])
        jobs.append(item["job"])
        os.replace(mine, os.path.join(d["done"], n))
    retry = _retry(jobs)
    return {"saved": saved, "refused": refused, "retry": retry}


def _retry(jobs):
    """One batch in batches/inbox for the answered jobs that are not submitted yet (deduped by URL)."""
    if not jobs:
        return 0
    from engine.pipeline import latest_status
    st, seen, out = latest_status(), set(), []
    for job in dict.fromkeys(jobs):
        e = find_entry(job)
        if not e or e.get("url") in seen or st.get(e.get("url")) == "SUBMITTED":
            continue
        seen.add(e["url"])
        out.append(e)
    if out:
        os.makedirs(os.path.join(BOX, "inbox"), exist_ok=True)
        name = f"answers_{time.strftime('%Y%m%d_%H%M%S')}.json"
        tmp = os.path.join(BOX, "inbox", "." + name)
        json.dump(out, open(tmp, "w", encoding="utf-8"), indent=1)
        os.replace(tmp, os.path.join(BOX, "inbox", name))
        record("answer_retry", batch=name, jobs=len(out))
    return len(out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    from engine.supervisor import beat
    while True:
        r = drain()
        if r.get("saved") or r.get("refused"):
            print(f"answers: {json.dumps(r)}", flush=True)
        waiting = len([n for n in os.listdir(_dirs()["inbox"]) if n.endswith(".json")])
        beat("answers", state="held: kill switch" if r.get("held") else "watching", waiting=waiting)
        if "--watch" not in argv:
            return r
        time.sleep(5)


if __name__ == "__main__":
    main()
