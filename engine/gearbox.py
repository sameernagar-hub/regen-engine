"""The gearbox: one control that sets how hard the engine runs, plus the clutch that couples the feedback loop to it.

  python -m engine gear                 show the gear, the clutch and what they set
  python -m engine gear N|1|2|3|4       shift (N = neutral: no new passes, appliers scale down to 0)
  python -m engine gear --clutch on|off on = learned rejection phrases block postings; off = base fit gate only

workspace/gear.json is the single source: the supervisor reads the applier range through limits() (gear.json wins
over fleet_limits.json), the pipeline reads the scan interval every pass, and tailor.fit() reads the clutch.
Safety limits are not gears: the daily cap (REGEN_MAX_PER_DAY), Ashby 1 per pass and HARD_MAX stay where they are.
"""
import json, os, sys, time

from engine.config import WORKSPACE

PATH = os.path.join(WORKSPACE, "gear.json")
# gear -> (min appliers, max appliers, minutes between scans). Gear 3 is the 10-18 start command.
GEARS = {
    "N": {"appliers": (0, 0), "loop_min": None, "label": "neutral: engine idles, nothing new is applied"},
    "1": {"appliers": (1, 1), "loop_min": 10, "label": "crawl: one applier, scan every 10 min"},
    "2": {"appliers": (1, 3), "loop_min": 5, "label": "cruise: up to 3 appliers, scan every 5 min"},
    "3": {"appliers": (1, 7), "loop_min": 3, "label": "drive: up to 7 appliers, scan every 3 min"},
    "4": {"appliers": (2, 9), "loop_min": 2, "label": "overdrive: 2-9 appliers, scan every 2 min"},
}
DEFAULT = {"gear": "3", "clutch": "on"}


def read():
    """{gear, clutch, set_at, by} with defaults; never raises."""
    try:
        g = {**DEFAULT, **json.load(open(PATH, encoding="utf-8"))}
    except (OSError, ValueError):
        g = dict(DEFAULT)
    if g["gear"] not in GEARS:
        g["gear"] = DEFAULT["gear"]
    if g["clutch"] not in ("on", "off"):
        g["clutch"] = "on"
    return g


def spec(g=None):
    g = g or read()
    return {**g, **GEARS[g["gear"]], "gears": {k: v["label"] for k, v in GEARS.items()}}


def shift(gear=None, clutch=None, by="operator"):
    """Write the new gear / clutch atomically and record a `gear` event. Raises ValueError on an unknown value."""
    g = read()
    if gear is not None:
        gear = str(gear).upper()
        if gear not in GEARS:
            raise ValueError(f"gear must be one of {', '.join(GEARS)}")
        g["gear"] = gear
    if clutch is not None:
        if clutch not in ("on", "off"):
            raise ValueError("clutch must be on or off")
        g["clutch"] = clutch
    g.update(set_at=time.strftime("%Y-%m-%d %H:%M:%S"), by=by)
    tmp = PATH + ".tmp"
    json.dump(g, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, PATH)
    from engine.feedback.events import record
    record("gear", gear=g["gear"], clutch=g["clutch"], by=by)
    return spec(g)


def appliers():
    """(min, max) for the supervisor, or None when no gear was ever set (then fleet_limits / env decide)."""
    return GEARS[read()["gear"]]["appliers"] if os.path.exists(PATH) else None


def loop_minutes(default):
    """Minutes until the next scan; None in neutral (the pipeline idles)."""
    if not os.path.exists(PATH):
        return default
    return GEARS[read()["gear"]]["loop_min"]


def clutch_engaged():
    return read()["clutch"] == "on"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv[:1] == ["--clutch"] and len(argv) > 1:
            s = shift(clutch=argv[1])
        elif argv:
            s = shift(gear=argv[0])
        else:
            s = spec()
    except ValueError as e:
        raise SystemExit(str(e))
    print(f"gear {s['gear']} ({s['label']}), clutch {s['clutch']}")
    return s


if __name__ == "__main__":
    main()
