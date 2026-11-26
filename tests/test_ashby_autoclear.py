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


def test_every_reader_and_writer_shares_one_cooldown_path_in_the_workspace():
    """11-25: the runner kept a relative ./ashby_cooldown (its cwd, lost on recreate) while the supervisor watched the workspace."""
    import os
    from engine import config
    from engine.apply import runner
    from apps.api import control
    assert os.path.isabs(config.ASHBY_COOLDOWN)
    assert config.ASHBY_COOLDOWN == os.path.join(config.WORKSPACE, "ashby_cooldown")
    assert S.ASHBY_COOLDOWN == runner.ASHBY_COOLDOWN == control.ASHBY_COOLDOWN == config.ASHBY_COOLDOWN


def test_the_runner_reads_the_shared_cooldown(tmp_path, monkeypatch):
    import datetime
    from engine.apply import runner
    f = tmp_path / "ashby_cooldown"
    monkeypatch.setattr(runner, "ASHBY_COOLDOWN", str(f))
    assert runner.ashby_cooling() is False
    f.write_text(datetime.datetime.now().isoformat())
    assert runner.ashby_cooling() is True
