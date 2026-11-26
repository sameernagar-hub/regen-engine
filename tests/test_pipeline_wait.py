"""11-25: the pipeline starts the next pass once the inbox has drained, not after the slowest batch finishes."""
import os

from engine import pipeline as P


def dirs(tmp_path):
    d = {k: str(tmp_path / k) for k in ("inbox", "claimed", "done")}
    for p in d.values():
        os.makedirs(p)
    return d


def put(d, kind, name):
    open(os.path.join(d[kind], name), "w").write("[]")


def test_one_slow_claimed_batch_does_not_block_the_next_pass(tmp_path):
    d = dirs(tmp_path)
    names = ["b0.json", "b1.json", "b2.json"]
    put(d, "done", "b0.json"); put(d, "done", "b1.json"); put(d, "claimed", "b2.json")
    assert P._settled(names, d, live_appliers=3) is True


def test_waits_while_two_or_more_batches_are_unclaimed(tmp_path):
    d = dirs(tmp_path)
    names = ["b0.json", "b1.json", "b2.json"]
    put(d, "inbox", "b1.json"); put(d, "inbox", "b2.json"); put(d, "claimed", "b0.json")
    assert P._settled(names, d, live_appliers=3) is False
    os.remove(os.path.join(d["inbox"], "b2.json")); put(d, "done", "b2.json")  # one left in the inbox: go
    assert P._settled(names, d, live_appliers=3) is True


def test_claimed_batches_without_a_live_applier_keep_it_waiting(tmp_path):
    d = dirs(tmp_path)
    put(d, "claimed", "b0.json"); put(d, "claimed", "b1.json")
    assert P._settled(["b0.json", "b1.json"], d, live_appliers=1) is False  # one was lost with its container
    assert P._settled(["b0.json", "b1.json"], d, live_appliers=2) is True


def test_wait_returns_early_and_never_on_unknown_fleet(tmp_path, monkeypatch):
    from engine.apply import worker
    d = dirs(tmp_path)
    monkeypatch.setattr(worker, "DIRS", d)
    monkeypatch.setattr(P, "beat", lambda *a, **k: None)
    monkeypatch.setattr(P.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("must not sleep")))
    put(d, "claimed", "b0.json")
    monkeypatch.setattr(P, "_live_appliers", lambda: 2)
    P._wait(["b0.json"])  # returns at once: the only batch is claimed by a live applier
    monkeypatch.setattr(P, "_live_appliers", lambda: 0)  # unknown / none: waits (until the timeout, here zero)
    P._wait(["b0.json"], timeout_h=0)


def test_select_skips_jobs_still_in_flight_so_overlapping_passes_never_double_dispatch(monkeypatch):
    from engine import targeting
    jobs = [{"company": "Acme", "title": "Software Engineer", "url": "u1", "id": "1"},
            {"company": "Globex", "title": "Software Engineer", "url": "u2", "id": "2"}]
    monkeypatch.setattr(targeting, "room_today", lambda events=None: 50)
    monkeypatch.setattr(P, "latest_status", lambda: {})
    monkeypatch.setattr(P, "history", lambda: (set(), set()))
    monkeypatch.setattr(P, "capped", lambda: set())
    monkeypatch.setattr(P, "in_flight", lambda: set())
    free = {j["url"] for j in P.select(list(jobs), 5)}
    monkeypatch.setattr(P, "in_flight", lambda: {P.role_key("Acme - Software Engineer")})  # still claimed by a slow applier
    again = {j["url"] for j in P.select(list(jobs), 5)}
    assert "u1" in free and "u1" not in again and (free - again) == {"u1"}
