"""Job priority: apply to the best-fitting, most-likely-to-answer jobs first, so a great job never waits behind
fifty average ones.

Two passes, both cheap:
  score(job)          before any description is fetched: title fit + level fit + freshness + employer tier +
                      what the inbox has taught us (response rate by lane). Used to order the queue. O(1) per job.
  jd_match(coverage)  after the full description is read: the share of the posting's terms the Fact Bank covers.
                      Used to order the built batch, so the highest JD match is applied to first.

The employer tier list is personal (which companies the user cares about most, which sponsor visas), so it lives in
profile/priority.json (git-ignored), shaped like profile.example/priority.json:
  {"tier1": "regex of employers", "tier2": "regex", "sponsors": "regex of known visa sponsors"}
Every score is logged with its parts, so the order is explainable in the control room.
"""
import datetime, json, os, re

from engine.config import profile_file

LEVEL_BOOST = re.compile(r"new grad|new graduate|early career|entry|junior|\bjr\b|associate|university|graduate|"
                         r"engineer i\b|\bswe i\b|software engineer 1\b|\bl3\b|level 1", re.I)
LEVEL_OK = re.compile(r"\bii\b|\b2\b|mid|intermediate|\bl4\b", re.I)
LANE_WORDS = {  # title words for the user's strongest lanes (Fact Bank depth), weight per lane
    "ai": (re.compile(r"\bai\b|machine learning|\bml\b|llm|genai|gen ai|applied ai|agent", re.I), 3),
    "backend": (re.compile(r"backend|back-end|platform|infrastructure|distributed|api", re.I), 2),
    "fullstack": (re.compile(r"full.?stack|product engineer|founding", re.I), 2),
    "general": (re.compile(r"software (engineer|developer)|\bswe\b|\bsde\b", re.I), 1),
}
_TIERS = {"mtime": None, "rx": {}}


def tiers():
    """Compiled tier regexes from profile/priority.json, re-read when the file changes. O(1) amortized."""
    try:
        p = profile_file("priority.json")
        m = os.path.getmtime(p)
    except (OSError, TypeError):
        return {}
    if _TIERS["mtime"] != m:
        raw = json.load(open(p, encoding="utf-8"))
        _TIERS.update(mtime=m, rx={k: re.compile(v, re.I) for k, v in raw.items() if not k.startswith("_") and v})
    return _TIERS["rx"]


def _hours_old(posted):
    try:
        t = datetime.datetime.fromisoformat((posted or "").replace("Z", "+00:00"))
        now = datetime.datetime.now(t.tzinfo) if t.tzinfo else datetime.datetime.now()
        return max(0.0, (now - t).total_seconds() / 3600)
    except ValueError:
        return 72.0


def score(job, lane_rates=None):
    """(score, parts) for one queued job. Higher = apply sooner. Parts are kept for the log/UI."""
    title, co = job.get("title", ""), job.get("company", "")
    parts = {}
    if LEVEL_BOOST.search(title):
        parts["level"] = 4  # postings written for the user's level answer more often
    elif LEVEL_OK.search(title):
        parts["level"] = 2
    for lane, (rx, w) in LANE_WORDS.items():
        if rx.search(title):
            parts["lane"] = max(parts.get("lane", 0), w)
    h = _hours_old(job.get("posted"))
    parts["fresh"] = round(4 * 0.5 ** (h / 24), 2)  # halves every day: being early matters most in the first hours
    t = tiers()
    if t.get("tier1") and t["tier1"].search(co):
        parts["tier"] = 4
    elif t.get("tier2") and t["tier2"].search(co):
        parts["tier"] = 2
    if t.get("sponsors") and t["sponsors"].search(co):
        parts["sponsor"] = 2
    if lane_rates:
        best = max((lane_rates.get(l, 0) for l, (rx, _) in LANE_WORDS.items() if rx.search(title)), default=0)
        if best:
            parts["learned"] = round(10 * best, 2)  # response rate by lane from the inbox (0..1)
    return round(sum(parts.values()), 2), parts


def jd_match(coverage):
    """Share of the posting's terms the Fact Bank covers (0..1), from tailor()'s coverage record."""
    have = len((coverage or {}).get("jd_terms_you_have") or [])
    on = len((coverage or {}).get("on_resume") or [])
    return round(on / have, 3) if have else 0.0


def lane_rates():
    """Response rate (any reply that isn't a plain confirmation) per lane, from outcome + resume events. O(E)."""
    from engine.feedback.events import read
    lane_of, sent, replied = {}, {}, {}
    for e in read():
        k = e.get("kind")
        if k == "resume" and e.get("job"):
            lane_of[e["job"]] = e.get("lane")
        elif k == "application" and (e.get("status") or "").startswith("SUBMITTED"):
            l = lane_of.get(e.get("job"))
            sent[l] = sent.get(l, 0) + 1
        elif k == "outcome" and e.get("outcome") in ("oa", "interview", "offer"):
            for j in e.get("jobs") or []:
                l = lane_of.get(j)
                replied[l] = replied.get(l, 0) + 1
    return {l: replied.get(l, 0) / n for l, n in sent.items() if l and n >= 5}
