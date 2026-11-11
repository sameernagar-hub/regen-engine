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


def test_cap_switch_levels_start_at_zero_and_clamp(tmp_path, monkeypatch, capsys):
    import pytest
    monkeypatch.setattr(targeting, "PROFILE", str(tmp_path))
    monkeypatch.setattr(targeting, "submitted_today", lambda events=None: 3)
    targeting._C.update(mtime=None)
    assert targeting.cap() == 15
    assert targeting.set_level("up") == (1, 25) and targeting.cap() == 25
    assert targeting.set_level("4") == (4, 150) and targeting.set_level("up") == (4, 150)
    assert targeting.set_level("0") == (0, 15) and targeting.set_level("down") == (0, 15)
    with pytest.raises(ValueError):
        targeting.set_level("9")
    targeting.main(["2"])
    assert "level 2 = 50" in capsys.readouterr().out
    assert json.loads((tmp_path / "targeting.json").read_text())["cap_level"] == 2


def test_unsure_flags_thin_or_low_share_overlap():
    cfg = dict(targeting.DEFAULTS)
    assert targeting.unsure("jd", ["python", "sql"], cfg, lacking=[]).startswith("unsure fit: Fact Bank covers 2 ")
    five = ["python", "sql", "aws", "docker", "react"]
    assert targeting.unsure("jd", five, cfg, lacking=["a"] * 4) is None  # 5 / 9 = 56%
    why = targeting.unsure("jd", five, cfg, lacking=["kotlin", "swift", "objc", "xcode", "gradle", "ios", "android", "jetpack"])
    assert why.startswith("unsure fit: Fact Bank covers 38%") and "kotlin" in why


def test_unsure_off_and_thresholds_from_settings():
    cfg = dict(targeting.DEFAULTS, skip_unsure=False)
    assert targeting.unsure("jd", [], cfg, lacking=["x"] * 50) is None
    cfg = dict(targeting.DEFAULTS, unsure_min_terms=1, unsure_min_share=0.1)
    assert targeting.unsure("jd", ["python"], cfg, lacking=["x"] * 5) is None
