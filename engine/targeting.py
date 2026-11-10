"""Targeting settings (NEXT_STEPS 3, decided by the user 2026-11-09: "use the defaults").

Volume did not move the funnel (446 verified, 1 OA, 0 interviews), so selection aims instead of filling the gearbox.
Settings live in profile/targeting.json (any key may be left out; DEFAULTS fill the rest), never in code constants:

  cap_levels    the daily caps the cap switch moves between, level 0 first (default 15, 25, 50, 100, 150)
  cap_level     the current level (0 = the agreed 15/day); `python -m engine cap 0|1|...|up|down` changes it
  daily_cap     cap used only when cap_levels is empty. select() queues nothing once the cap is reached
                (REGEN_MAX_PER_DAY stays the runner's hard backstop)
  tier_first    tier1 and visa-sponsor employers (profile/priority.json) go before every other job, then freshest
  skip_unsure   (planned) skip roles where the fit gate is unsure instead of submitting and hoping
  keywords_ab   (planned) Role Keywords on/off by a hash of the posting URL; `ab_per_arm` submissions per arm
                before anyone reads the result, and no early stop because one arm looks ahead
O(1) per call after the first read (re-read when the file changes).
"""
import datetime, json, os

from engine.config import PROFILE

DEFAULTS = {"cap_levels": [15, 25, 50, 100, 150], "cap_level": 0, "daily_cap": 15, "tier_first": True, "skip_unsure": True, "keywords_ab": False, "ab_per_arm": 150}
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


def cap(cfg=None):
    """Today's cap: cap_levels[cap_level] (clamped to the list), else daily_cap."""
    cfg = cfg or load()
    levels = cfg.get("cap_levels") or []
    if not levels:
        return int(cfg["daily_cap"])
    return int(levels[max(0, min(int(cfg.get("cap_level") or 0), len(levels) - 1))])


def set_level(arg):
    """Move the cap switch: a level number, "up" or "down" (clamped). Writes profile/targeting.json, keeping the
    other keys. Returns (level, cap)."""
    cfg = load()
    levels = cfg.get("cap_levels") or [int(cfg["daily_cap"])]
    cur = max(0, min(int(cfg.get("cap_level") or 0), len(levels) - 1))
    new = cur + 1 if arg == "up" else cur - 1 if arg == "down" else int(arg)
    if not 0 <= new < len(levels):
        if arg in ("up", "down"):
            new = cur
        else:
            raise ValueError(f"level must be 0..{len(levels) - 1}")
    p = os.path.join(PROFILE, "targeting.json")
    try:
        raw = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    raw["cap_level"] = new
    tmp = p + ".tmp"
    json.dump(raw, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, p)
    _C.update(mtime=None)
    return new, int(levels[new])


def main(argv=None):
    import sys
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        set_level(argv[0])
    cfg = load()
    levels = cfg.get("cap_levels") or [int(cfg["daily_cap"])]
    lvl = max(0, min(int(cfg.get("cap_level") or 0), len(levels) - 1))
    marks = "  ".join(f"[{i}:{c}]" if i == lvl else f"{i}:{c}" for i, c in enumerate(levels))
    print(f"daily cap level {lvl} = {cap(cfg)} submissions/day ({submitted_today()} today)   {marks}")


def submitted_today(events=None):
    from engine.feedback.events import read
    today = datetime.date.today().isoformat()
    return sum(1 for e in (read("application") if events is None else events)
               if (e.get("status") or "").startswith("SUBMITTED") and not e.get("dry") and (e.get("ts") or "").startswith(today))


def room_today(events=None):
    """How many more submissions today's cap allows (never negative)."""
    return max(0, cap() - submitted_today(events))


def tier_rank(job, tiers):
    """0 = tier1 or a known visa sponsor (or the portal says it sponsors), 1 = everyone else."""
    co = job.get("company", "")
    if any(tiers.get(k) and tiers[k].search(co) for k in ("tier1", "sponsors")) or job.get("h1b") is True:
        return 0
    return 1
