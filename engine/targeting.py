"""Targeting settings (NEXT_STEPS 3, decided by the user 2026-11-09: "use the defaults").

Volume did not move the funnel (446 verified, 1 OA, 0 interviews), so selection aims instead of filling the gearbox.
Settings live in profile/targeting.json (any key may be left out; DEFAULTS fill the rest), never in code constants:

  daily_cap     at most this many verified submissions per day; select() queues nothing once it is reached
                (REGEN_MAX_PER_DAY stays the runner's hard backstop)
  tier_first    tier1 and visa-sponsor employers (profile/priority.json) go before every other job, then freshest
  skip_unsure   (planned) skip roles where the fit gate is unsure instead of submitting and hoping
  keywords_ab   (planned) Role Keywords on/off by a hash of the posting URL; `ab_per_arm` submissions per arm
                before anyone reads the result, and no early stop because one arm looks ahead
O(1) per call after the first read (re-read when the file changes).
"""
import datetime, json, os

from engine.config import PROFILE

DEFAULTS = {"daily_cap": 15, "tier_first": True, "skip_unsure": True, "keywords_ab": False, "ab_per_arm": 150}
_C = {"mtime": None, "cfg": dict(DEFAULTS)}


def load():
    p = os.path.join(PROFILE, "targeting.json")
    try:
        m = os.path.getmtime(p)
    except OSError:
        return dict(DEFAULTS)
    if _C["mtime"] != m:
        try:
            raw = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        _C.update(mtime=m, cfg={**DEFAULTS, **{k: v for k, v in raw.items() if k in DEFAULTS}})
    return dict(_C["cfg"])


def submitted_today(events=None):
    from engine.feedback.events import read
    today = datetime.date.today().isoformat()
    return sum(1 for e in (read("application") if events is None else events)
               if (e.get("status") or "").startswith("SUBMITTED") and not e.get("dry") and (e.get("ts") or "").startswith(today))


def room_today(events=None):
    """How many more submissions today's cap allows (never negative)."""
    return max(0, int(load()["daily_cap"]) - submitted_today(events))


def tier_rank(job, tiers):
    """0 = tier1 or a known visa sponsor (or the portal says it sponsors), 1 = everyone else."""
    co = job.get("company", "")
    if any(tiers.get(k) and tiers[k].search(co) for k in ("tier1", "sponsors")) or job.get("h1b") is True:
        return 0
    return 1
