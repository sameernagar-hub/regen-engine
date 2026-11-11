"""Targeting settings (NEXT_STEPS 3, decided by the user 2026-11-09: "use the defaults").

Volume did not move the funnel (446 verified, 1 OA, 0 interviews), so selection aims instead of filling the gearbox.
Settings live in profile/targeting.json (any key may be left out; DEFAULTS fill the rest), never in code constants:

  cap_levels    the daily caps the cap switch moves between, level 0 first (default 15, 25, 50, 100, 150)
  cap_level     the current level (0 = the agreed 15/day); `python -m engine cap 0|1|...|up|down` changes it
  daily_cap     cap used only when cap_levels is empty. select() queues nothing once the cap is reached
                (REGEN_MAX_PER_DAY stays the runner's hard backstop)
  tier_first    tier1 and visa-sponsor employers (profile/priority.json) go before every other job, then freshest
  skip_unsure   skip roles where the fit gate is unsure instead of submitting and hoping. The gate only knows hard
                blockers; a posting with none can still be one the Fact Bank barely touches. "Unsure" = the Fact Bank
                covers fewer than `unsure_min_terms` of the posting's terms, or under `unsure_min_share` of them
                (covered / (covered + JD tech terms the Fact Bank lacks)). Recorded as SKIPPED "unsure fit: ..."
                so the funnel can count it; set skip_unsure false to send them again
  keywords_ab   Role Keywords on/off by a hash of the posting URL (keywords.arm), overriding the per-run switch while
                on (REGEN_JD_KEYWORDS still wins); the arm is logged in the resume event (ab_arm). `report ab`
                shows rates only once both arms reach `ab_per_arm` verified submissions: no early stop
O(1) per call after the first read (re-read when the file changes).
"""
import datetime, json, os

from engine.config import PROFILE

DEFAULTS = {"cap_levels": [15, 25, 50, 100, 150], "cap_level": 0, "daily_cap": 15, "tier_first": True, "skip_unsure": True, "keywords_ab": False, "ab_per_arm": 150,
            "unsure_min_terms": 5, "unsure_min_share": 0.4}
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
    from engine.feedback.events import record  # the revamp's `cap` event (docs/ALIVE_PLAN.md §5a), CLI or API alike
    record("cap", level=new, cap=int(levels[new]))
    return new, int(levels[new])


SETTABLE = {"tier_first": bool, "skip_unsure": bool, "keywords_ab": bool, "unsure_min_terms": int, "unsure_min_share": float}


def set_option(key, value):
    """Change one targeting setting (API / CLI), typed and range-checked; writes profile/targeting.json keeping the
    other keys and records a `targeting` event. cap_level goes through set_level; ab_per_arm is fixed before the A/B
    starts, so it is not settable here (no moving the goalposts). Returns the new settings."""
    if key not in SETTABLE:
        raise ValueError(f"{key} is not settable (one of {', '.join(SETTABLE)})")
    t = SETTABLE[key]
    if t is bool:
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false")
    else:
        try:
            value = t(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be a number")
        if (key == "unsure_min_share" and not 0 <= value <= 1) or (key == "unsure_min_terms" and not 0 <= value <= 50):
            raise ValueError(f"{key} out of range")
    p = os.path.join(PROFILE, "targeting.json")
    try:
        raw = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    raw[key] = value
    tmp = p + ".tmp"
    json.dump(raw, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, p)
    _C.update(mtime=None)
    from engine.feedback.events import record
    record("targeting", key=key, value=value)
    return load()


def status(events=None):
    """Everything the cap dial and the targeting panel show: settings, level, today's cap and count."""
    cfg = load()
    levels = cfg.get("cap_levels") or [int(cfg["daily_cap"])]
    return {**cfg, "cap_level": max(0, min(int(cfg.get("cap_level") or 0), len(levels) - 1)), "cap": cap(cfg),
            "today": submitted_today(events)}


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


_BANK = {"key": None, "text": ""}


def _bank_text():
    """Every wording in the Fact Bank (facts, variants, skills, projects) as one string; built once per loaded bank."""
    from engine.tailoring import resume
    resume.load_bank()
    if _BANK["key"] is not resume.FACTS:
        parts = [t for f in resume.FACTS for t in resume.texts(f)]
        parts += [v[1] for v in resume.SKILLS.values()]
        parts += [" ".join([p[0]] + list(p[2])) for p in resume.PROJECTS.values()]
        _BANK.update(key=resume.FACTS, text=" ".join(parts))
    return _BANK["text"]


def unsure(jd, covered, cfg=None, lacking=None):
    """Why the fit is unsure (a short reason), or None when the posting is a clear fit or skip_unsure is off.
    covered = the posting's terms the Fact Bank has (tailor()'s jd_terms_you_have); lacking = JD tech terms the bank
    lacks (computed from the bank when not given). O(JD + bank) per posting."""
    cfg = cfg or load()
    if not cfg.get("skip_unsure"):
        return None
    have = len(covered)
    if have < int(cfg["unsure_min_terms"]):
        return f"unsure fit: Fact Bank covers {have} of the posting's terms (min {cfg['unsure_min_terms']})"
    if lacking is None:
        from engine.tailoring import keywords
        lacking = keywords.missing(jd, _bank_text())
    share = have / (have + len(lacking))
    if share < float(cfg["unsure_min_share"]):
        return (f"unsure fit: Fact Bank covers {share:.0%} of the posting's terms (min {float(cfg['unsure_min_share']):.0%};"
                f" lacks {', '.join(lacking[:5])})")
    return None
