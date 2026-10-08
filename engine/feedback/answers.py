"""Answer from the page (v0.8): the user answers a "waiting on you" question once, in the web app, and the engine
reuses it on every future form.

Write path, behind the same airbags as everything else:
  - Only the local API can write, and only when REGEN_API_WRITE=1 (the public deploy never sets it).
  - Legal, sponsorship, EEO and sensitive questions are refused here: those answers come from presets only.
  - The answer is stored in profile/answers.json as {pattern, answer, source}; pattern is the question itself,
    escaped (it matches that exact wording, case- and spacing-insensitive), never a broad regex from the browser.
  - An `answer` event records who/what/when, and the job is put back on workspace/batches/requeue.json so the
    next `engine apply batches/requeue.json` retries it with the new answer.
"""
import datetime, json, os, re

from engine.apply.drafts import NEVER
from engine.config import PROFILE, WORKSPACE
from engine.feedback.events import read, record

LEGAL_OR_SENSITIVE = re.compile(NEVER.pattern + r"|arbitrat|eeo|ethnic|orientation|hispanic|latin|transgender", re.I)
MAX_ANSWER = 2000


def pattern_for(question):
    q = " ".join((question or "").split()).lower().rstrip("*").strip()
    return re.escape(q)[:300]


def missing_questions(detail):
    """'NEEDS YOU: Q1 | Q2' -> ['Q1', 'Q2'] (the labels the runner could not answer)."""
    d = detail or ""
    if not d.startswith("NEEDS YOU:"):
        return []
    return [q.strip() for q in d[len("NEEDS YOU:"):].split(" | ") if q.strip() and not q.strip().startswith(("no adapter", "Ashby cooldown"))]


def save(job, question, answer, profile=None, workspace=None):
    """Validate and store one answer. Returns the stored record; raises ValueError with a reason when refused."""
    profile, workspace = profile or PROFILE, workspace or WORKSPACE
    question, answer = " ".join((question or "").split()), (answer or "").strip()
    if not question or not answer:
        raise ValueError("question and answer are required")
    if len(answer) > MAX_ANSWER:
        raise ValueError(f"answer longer than {MAX_ANSWER} characters")
    if LEGAL_OR_SENSITIVE.search(question):
        raise ValueError("legal, sponsorship, EEO and sensitive questions are answered from presets only")
    path = os.path.join(profile, "answers.json")
    bank = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    pat = pattern_for(question)
    rec = {"pattern": pat, "answer": answer, "source": f"web app, {datetime.datetime.now().isoformat(timespec='seconds')}, for {job}"}
    bank = [b for b in bank if b.get("pattern") != pat] + [rec]
    tmp = path + ".tmp"
    json.dump(bank, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(tmp, path)  # atomic: a reader never sees half a file
    record("answer", job=job, question=question[:300], pattern=pat, source="web app")
    requeue(job, workspace)
    return rec


def requeue(job, workspace=None):
    """Put the job's batch entry on batches/requeue.json (deduped by URL). Returns True if found."""
    workspace = workspace or WORKSPACE
    bdir = os.path.join(workspace, "batches")
    entry = None
    if os.path.isdir(bdir):
        for f in sorted(os.listdir(bdir), key=lambda f: os.path.getmtime(os.path.join(bdir, f)), reverse=True):
            if not f.endswith(".json") or f == "requeue.json":
                continue
            try:
                entry = next((j for j in json.load(open(os.path.join(bdir, f), encoding="utf-8")) if j.get("name") == job), None)
            except (OSError, ValueError):
                continue
            if entry:
                break
    if not entry:
        return False
    os.makedirs(bdir, exist_ok=True)
    rq = os.path.join(bdir, "requeue.json")
    cur = json.load(open(rq, encoding="utf-8")) if os.path.exists(rq) else []
    if all(j.get("url") != entry.get("url") for j in cur):
        cur.append({k: v for k, v in entry.items() if not k.startswith("_")})
        json.dump(cur, open(rq, "w", encoding="utf-8"), indent=1)
    return True


def drafted(limit=200):
    """Drafted answers that were sent without waiting (newest first), for review in the web app."""
    out = []
    for e in read("application"):
        for q, a, fids in e.get("drafted") or []:
            out.append({"ts": e["ts"], "job": e.get("job"), "status": (e.get("status") or "").split(":")[0],
                        "question": q, "answer": a, "facts": fids})
    return out[::-1][:limit]
