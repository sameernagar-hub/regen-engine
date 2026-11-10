"""Targeting (NEXT_STEPS 3): settings come from profile/targeting.json, the cap stops selection, tier1 / sponsors first."""
import datetime, json, re

from engine import targeting


def test_defaults_and_file_override(tmp_path, monkeypatch):
    monkeypatch.setattr(targeting, "PROFILE", str(tmp_path))
    targeting._C.update(mtime=None)
    assert targeting.load() == targeting.DEFAULTS
    (tmp_path / "targeting.json").write_text(json.dumps({"daily_cap": 5, "junk": 1}), encoding="utf-8")
    cfg = targeting.load()
    assert cfg["daily_cap"] == 5 and "junk" not in cfg and cfg["tier_first"] is True


def test_room_today_counts_only_todays_real_submits(tmp_path, monkeypatch):
    monkeypatch.setattr(targeting, "PROFILE", str(tmp_path))
    today = datetime.date.today().isoformat()
    evs = ([{"status": "SUBMITTED", "ts": today + "T10:00:00"}] * 14 + [{"status": "SUBMITTED", "ts": "2020-01-01T00:00:00"},
           {"status": "SUBMITTED", "ts": today + "T11:00:00", "dry": True}, {"status": "NEEDS YOU", "ts": today + "T12:00:00"}])
    assert targeting.room_today(evs) == 1
    assert targeting.room_today(evs + [{"status": "SUBMITTED (verified)", "ts": today + "T13:00:00"}] * 3) == 0


def test_tier_rank_puts_tier1_and_sponsors_first():
    t = {"tier1": re.compile("bigco", re.I), "sponsors": re.compile("visaco", re.I)}
    ranks = [targeting.tier_rank({"company": c}, t) for c in ("BigCo", "VisaCo", "SmallCo")]
    assert ranks == [0, 0, 1] and targeting.tier_rank({"company": "x", "h1b": True}, t) == 0


def test_select_stops_at_the_daily_cap(monkeypatch):
    from engine import pipeline
    monkeypatch.setattr(targeting, "room_today", lambda events=None: 0)
    monkeypatch.setattr(pipeline, "in_flight", lambda: set())
    monkeypatch.setattr(pipeline, "latest_status", lambda: {})
    monkeypatch.setattr(pipeline, "history", lambda: (set(), set()))
    monkeypatch.setattr(pipeline, "capped", lambda: set())
    assert pipeline.select([{"company": "A", "title": "Software Engineer", "url": "u"}], 5) == []
