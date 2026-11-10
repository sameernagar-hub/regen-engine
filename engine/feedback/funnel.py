"""Outcome funnel: what the applications led to (docs/NEXT_STEPS.md §1.2; §2 adds the splits).

  python -m engine report rate     interviews and OAs per 100 verified applications, with a 95% interval

The one number every volume figure is shown beside. An application counts only when verified (latest status
SUBMITTED and its proof screenshot on disk, the same rule as `python -m engine report`); an outcome counts when the
mail classifier (engine/feedback/inbox.py) tied an OA / interview / offer mail to that job. Counts are small, so every
rate carries a Wilson interval and the text says so when the data cannot tell two rates apart.
"""
import math
import os

from engine.config import WORKSPACE
from engine.feedback.events import read

POSITIVE = ("oa", "interview", "offer")


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes in n trials, as (low, high) fractions. (0, 0) when n is 0.
    Wilson, not the normal approximation: it stays inside 0..1 and behaves when k is 0 or tiny, which is our case."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, mid - half), min(1.0, mid + half))


def verified(day=None):
    """Latest application event per job where the status is SUBMITTED and the proof screenshot exists."""
    latest = {}
    for e in read("application"):
        if not e.get("dry"):
            latest[e.get("url") or e["job"]] = e
    rows = [e for e in latest.values() if e["status"] == "SUBMITTED" and (not day or e["ts"].startswith(day))]
    return [e for e in rows if e.get("proof") and os.path.exists(os.path.join(WORKSPACE, e["proof"]))], rows


def outcomes():
    """job -> set of outcome labels the inbox classifier recorded for it."""
    outs = {}
    for o in read("outcome"):
        for j in o.get("jobs", []):
            outs.setdefault(j, set()).add(o["outcome"])
    return outs


def rate(apps=None, outs=None):
    """Counts and per-100 rates over verified applications. A job with both an OA and an interview counts once in
    `positive` (the headline: applications that reached a person or a test)."""
    apps = verified()[0] if apps is None else apps
    outs = outcomes() if outs is None else outs
    n = len(apps)
    got = [outs.get(e["job"], set()) for e in apps]
    out = {"verified": n}
    for name in POSITIVE:
        out[name] = sum(1 for s in got if name in s)
    out["positive"] = sum(1 for s in got if s & set(POSITIVE))
    out["rejection"] = sum(1 for s in got if "rejection" in s)
    out["no_reply"] = sum(1 for s in got if not (s - {"confirmation"}))
    lo, hi = wilson(out["positive"], n)
    out["per_100"] = round(100 * out["positive"] / n, 1) if n else 0.0
    out["interval_per_100"] = (round(100 * lo, 1), round(100 * hi, 1))
    return out


def line(r):
    """The one-line form used in the README stats row and wiki Metrics."""
    lo, hi = r["interval_per_100"]
    return (f"{r['verified']} verified applications -> {r['oa']} OA, {r['interview']} interview, {r['offer']} offer: "
            f"{r['per_100']} per 100 reached an OA or interview (95% interval {lo} to {hi})")


def main(argv):
    r = rate()
    print(line(r))
    print(f"  rejections {r['rejection']}, no reply yet {r['no_reply']}")
    if r["interview"] == 0:
        print("  No interview on record yet. With this few positives, differences between lanes or settings are "
              "not significant; treat any split as a count, not a finding.")
