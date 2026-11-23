"""11-22: the supervisor clears the Ashby cooldown when the operator switched auto-clear on (off by default)."""
import json, os

from engine import supervisor as S


def test_ashby_autoclear(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "ASHBY_AUTOCLEAR", str(tmp_path / "ashby_autoclear.json"))
    monkeypatch.setattr(S, "ASHBY_COOLDOWN", str(tmp_path / "ashby_cooldown"))
    monkeypatch.setattr(S, "_own", lambda p: None)
    seen = []
    monkeypatch.setattr(S, "audit", lambda action, target, **kw: seen.append(action))
    cool = tmp_path / "ashby_cooldown"
    cool.write_text("2026-11-22T18:52:23")
    assert S.ashby_watch() is False and cool.exists()          # off by default: the cooldown stays
    assert S.control(["--ashby-autoclear", "on"]) == {"ashby_autoclear": True}
    assert S.ashby_watch() is True and not cool.exists()       # on: cleared and audited
    assert S.ashby_watch() is False                             # nothing to clear
    assert S.control(["--ashby-autoclear", "off"]) == {"ashby_autoclear": False}
    cool.write_text("x")
    assert S.ashby_watch() is False and cool.exists()
    assert seen == ["ashby_autoclear", "ashby_clear", "ashby_autoclear"]
