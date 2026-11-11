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


def outcomes(events=None, prefer=None):
    """job -> set of outcome labels the inbox classifier recorded for it.

    11-09 hand-check: the classifier attaches an employer's mail to EVERY role applied to there (one employer's
    assessment request was tied to 6 roles, which read as "5 OAs"). A rejection or confirmation may apply to all of
    them, but a positive (OA / interview / offer) at one employer is credited to ONE role: the first verified role
    (`prefer`) among those its mails named, else the first role named. The rate counts what happened, not how many
    roles a mail was matched to."""
    prefer = prefer or set()
    outs, positive = {}, {}
    for o in (read("outcome") if events is None else events):
        jobs = o.get("jobs", [])
        if o["outcome"] in POSITIVE and jobs:
            seen = positive.setdefault((o["outcome"], _company(jobs[0]).lower()), [])
            seen += [j for j in jobs if j not in seen]
            continue
        for j in jobs:
            outs.setdefault(j, set()).add(o["outcome"])
    for (label, _), jobs in positive.items():
        outs.setdefault(next((j for j in jobs if j in prefer), jobs[0]), set()).add(label)
    return outs


def rate(apps=None, outs=None):
    """Counts and per-100 rates over verified applications. A job with both an OA and an interview counts once in
    `positive` (the headline: applications that reached a person or a test)."""
    apps = verified()[0] if apps is None else apps
    outs = outcomes(prefer={a["job"] for a in apps}) if outs is None else outs
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


STAGES = ("verified", "replied", "oa", "interview", "offer")
DIMENSIONS = ("lane", "ats", "tier", "posting age", "role keywords", "answered by", "outreach")


def _company(job):
    return (job or "").split(" - ")[0].strip()


def _hours(posted, ts):
    import datetime
    try:
        p = datetime.datetime.fromisoformat(str(posted).replace("Z", "+00:00"))
        t = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if (p.tzinfo is None) != (t.tzinfo is None):  # ledger ts is local naive, boards give UTC: compare as naive UTC-ish
            p, t = p.replace(tzinfo=None), t.replace(tzinfo=None)
        return max(0.0, (t - p).total_seconds() / 3600)
    except (TypeError, ValueError):
        return None


def label(dim, app, res, tiers, drafted, sent=frozenset()):
    """The group one verified application falls in for one dimension. "not recorded" when the ledger lacks it:
    a missing value is never guessed (posting time and the keywords switch were first logged on 11-09)."""
    if dim == "lane":
        return res.get("lane") or "not recorded"
    if dim == "ats":
        if res.get("ats"):
            return res["ats"]
        from engine.pipeline import ats_of
        return ats_of(app.get("url"))
    if dim == "tier":
        co = _company(app["job"])
        return next((t for t in ("tier1", "tier2", "sponsors") if t in tiers and tiers[t].search(co)), "other")
    if dim == "posting age":
        h = _hours(res.get("posted"), app.get("ts"))
        return "not recorded" if h is None else "<6h" if h < 6 else "6-48h" if h <= 48 else ">48h"
    if dim == "role keywords":
        if "keywords_on" in res:
            return "on" if res["keywords_on"] else "off"
        if "jd_keywords" in res:
            return "on" if res["jd_keywords"] else "off"
        return "not recorded"
    if dim == "answered by":
        return app.get("answered_by") or "not recorded"
    if dim == "outreach":
        co = _company(app["job"]).lower()
        return "sent" if co in sent else "drafted" if co in drafted else "none"
    raise ValueError(dim)


def _counts(apps, outs):
    got = [outs.get(a["job"], set()) for a in apps]
    return {"verified": len(apps), "replied": sum(1 for s in got if s - {"confirmation"}),
            "oa": sum(1 for s in got if "oa" in s), "interview": sum(1 for s in got if "interview" in s),
            "offer": sum(1 for s in got if "offer" in s), "positive": sum(1 for s in got if s & set(POSITIVE))}


def _overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def funnel(apps=None, outs=None, resumes=None, tiers=None, drafted=None, sent=None):
    """{"overall": counts, "splits": {dim: [(group, counts, interval, significant)]}}. A group is "significant" only
    when its 95% interval for OA-or-interview does not overlap the interval of all other applications (conservative:
    with this few positives that is rare, and the report says so instead of reading noise as a finding)."""
    if apps is None:
        apps = verified()[0]
    outs = outcomes(prefer={a["job"] for a in apps}) if outs is None else outs
    if resumes is None:
        resumes = {}
        for r in read("resume"):
            resumes[r.get("url") or r["job"]] = r
    if tiers is None:
        from engine.discovery.priority import tiers as _t
        tiers = _t()
    if drafted is None:
        drafted = {(o.get("company") or "").lower() for o in read("outreach")} - {""}
    if sent is None:  # notes the user marked sent (`engine outreach sent <company>`): "applied + outreach"
        sent = {(o.get("company") or "").lower() for o in read("outreach_sent")} - {""}
    res_of = lambda a: resumes.get(a.get("url")) or resumes.get(a["job"]) or {}
    out = {"overall": _counts(apps, outs), "splits": {}}
    for dim in DIMENSIONS:
        groups = {}
        for a in apps:
            groups.setdefault(label(dim, a, res_of(a), tiers, drafted, sent), []).append(a)
        rows = []
        for g, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            c = _counts(members, outs)
            rest = _counts([a for a in apps if a not in members], outs)
            ci, ci_rest = wilson(c["positive"], c["verified"]), wilson(rest["positive"], rest["verified"])
            rows.append((g, c, ci, bool(rest["verified"]) and not _overlap(ci, ci_rest)))
        out["splits"][dim] = rows
    return out


def _pct(k, n):
    return f"{100 * k / n:.1f}" if n else "-"


def print_funnel(f):
    o = f["overall"]
    n = o["verified"]
    print("Funnel over all verified applications (outcomes from the mail classifier)")
    print("  " + " -> ".join(f"{s} {o[s]}" + ("" if s == "verified" else f" ({_pct(o[s], n)}%)") for s in STAGES))
    lo, hi = wilson(o["positive"], n)
    print(f"  OA or interview: {_pct(o['positive'], n)} per 100 (95% interval {100 * lo:.1f} to {100 * hi:.1f})")
    found = False
    for dim, rows in f["splits"].items():
        print(f"\nBy {dim}")
        print(f"  {'group':<16}{'sent':>6}{'reply':>7}{'OA':>5}{'intv':>6}{'per 100':>9}   95% interval")
        for g, c, (lo, hi), sig in rows:
            found |= sig
            print(f"  {str(g)[:16]:<16}{c['verified']:>6}{c['replied']:>7}{c['oa']:>5}{c['interview']:>6}"
                  f"{_pct(c['positive'], c['verified']):>9}   {100 * lo:.1f} to {100 * hi:.1f}" + ("   significant" if sig else ""))
    groups = sum(len(r) for r in f["splits"].values())
    print("\n" + (f"Some groups differ from the rest (marked). {groups} groups were compared, so one chance hit is "
                  "expected now and then: read the counts, and treat a mark as a lead to test (NEXT_STEPS §3), not proof." if found else
                  "No group differs significantly from the rest: these splits are counts, not findings. More outcomes "
                  "are needed before any setting can be credited or blamed."))


def ab(apps=None, outs=None, resumes=None, per_arm=None):
    """Role Keywords A/B (NEXT_STEPS §3): verified applications whose resume event logged an arm. Rates are returned
    only once BOTH arms reach per_arm (profile/targeting.json ab_per_arm, fixed before the start) - no peeking, no
    early stop because one arm looks ahead. {"per_arm", "n": {arm: count}, "ready", "rows": [(arm, counts, ci)]}."""
    from engine import targeting
    per_arm = int(targeting.load()["ab_per_arm"]) if per_arm is None else per_arm
    if apps is None:
        apps = verified()[0]
    if resumes is None:
        resumes = {}
        for r in read("resume"):
            resumes[r.get("url") or r["job"]] = r
    arm_of = lambda a: (resumes.get(a.get("url")) or resumes.get(a["job"]) or {}).get("ab_arm")
    groups = {"on": [], "off": []}
    for a in apps:
        if arm_of(a) in groups:
            groups[arm_of(a)].append(a)
    n = {k: len(v) for k, v in groups.items()}
    ready = min(n.values()) >= per_arm
    rows = []
    if ready:
        outs = outcomes(prefer={a["job"] for a in apps}) if outs is None else outs
        for k, members in groups.items():
            c = _counts(members, outs)
            rows.append((k, c, wilson(c["positive"], c["verified"])))
    return {"per_arm": per_arm, "n": n, "ready": ready, "rows": rows}


def print_ab(r):
    print(f"Role Keywords A/B: {r['n']['on']} verified with the line, {r['n']['off']} without (target {r['per_arm']} per arm)")
    if not r["ready"]:
        print("  Not read yet: rates stay hidden until both arms reach the target, so nobody stops early on noise.")
        return
    for k, c, (lo, hi) in r["rows"]:
        print(f"  {k:<4} sent {c['verified']:>4}  reply {c['replied']:>4}  OA {c['oa']:>3}  interview {c['interview']:>3}"
              f"  OA or interview {_pct(c['positive'], c['verified'])} per 100 (95% interval {100 * lo:.1f} to {100 * hi:.1f})")
    (_, _, a), (_, _, b) = r["rows"]
    print("  " + ("The intervals do not overlap: the arms differ." if not _overlap(a, b) else
                  "The intervals overlap: no difference shown at this sample size."))


def main(argv):
    if argv and argv[0] == "funnel":
        return print_funnel(funnel())
    if argv and argv[0] == "ab":
        return print_ab(ab())
    r = rate()
    print(line(r))
    print(f"  rejections {r['rejection']}, no reply yet {r['no_reply']}")
    if r["interview"] == 0:
        print("  No interview on record yet. With this few positives, differences between lanes or settings are "
              "not significant; treat any split as a count, not a finding.")
