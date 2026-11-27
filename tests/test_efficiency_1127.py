"""11-27 efficiency fixes: capped discovered cache, scan back-off, dead-board merge, host-memory hold."""
import json, time

from engine.feedback import events as E


def test_trim_discovered_keeps_newest_and_others():
    evs = [{"kind": "discovered", "i": i} for i in range(5)] + [{"kind": "application"}] + [{"kind": "discovered", "i": 9}]
    out = E.trim_discovered(evs, keep=2)
    assert [e.get("i") for e in out if e["kind"] == "discovered"] == [4, 9]
    assert sum(e["kind"] == "application" for e in out) == 1


def test_event_cache_caps_discovered(tmp_path, monkeypatch):
    p = tmp_path / "events.jsonl"
    p.write_text("".join(json.dumps({"kind": "discovered", "i": i}) + "\n" for i in range(50)) + json.dumps({"kind": "application"}) + "\n")
    monkeypatch.setattr(E, "_path", lambda: str(p))
    monkeypatch.setattr(E, "DISCOVERED_KEEP", 10)
    E._cache.update(path=None)
    evs = E.read()
    assert len([e for e in evs if e["kind"] == "discovered"]) <= 20 and len(E.read("application")) == 1
    assert evs[-1]["kind"] == "application" and max(e.get("i", -1) for e in evs) == 49


def test_scan_backs_off_after_empty_passes():
    from engine import pipeline as P
    assert P.idle_wait(3, 0) == 3 and P.idle_wait(3, 1) == 3
    assert P.idle_wait(3, 2) == P.IDLE_LOOP_MIN and P.idle_wait(30, 5) == 30


def test_save_boards_keeps_dead_marks_written_meanwhile(tmp_path, monkeypatch):
    from engine.discovery import ats as A
    path = tmp_path / "boards.json"
    monkeypatch.setattr(A, "boards_path", lambda: str(path))
    monkeypatch.setattr(A, "WORKSPACE", str(tmp_path))
    stale = {a: [] for a in A.ATS} | {"dead": ["greenhouse:old"]}
    path.write_text(json.dumps(stale | {"dead": ["greenhouse:old", "lever:new"]}))  # a scan marked lever:new
    A.save_boards(dict(stale, greenhouse=["acme"]))  # a harvest saves its older copy
    saved = json.loads(path.read_text())
    assert set(saved["dead"]) == {"greenhouse:old", "lever:new"} and saved["greenhouse"] == ["acme"]
    A.save_boards(dict(stale, dead=[]), merge_dead=False)  # boards recheck may shrink it
    assert json.loads(path.read_text())["dead"] == []


def test_governor_holds_when_host_is_short(tmp_path):
    from engine import governor as G
    vm = {"free_mb": 6000, "load_per_cpu": 0.1}
    c, _ = G.decide(1, 7, 2, vm, 800, {}, False)
    assert c > 2
    c, why = G.decide(1, 7, 2, dict(vm, host_free_mb=1000), 800, {}, False)
    assert c == 2 and any("host" in r for r in why)  # hold at running, never shed on the host signal
    base, _ = G.decide(1, 7, 2, vm, 800, {}, False)
    c, why = G.decide(1, 7, 2, dict(vm, host_free_mb=3200), 800, {}, False)
    assert c == base  # room on the host: the usual growth step
    f = tmp_path / "host.json"
    f.write_text(json.dumps({"free_mb": 900, "ts": time.time()}))
    assert G.host_free(str(f)) == 900
    f.write_text(json.dumps({"free_mb": 900, "ts": time.time() - 3600}))
    assert G.host_free(str(f)) is None
