"""events.read() under concurrent callers (11-13): the API's thread pool once doubled every count."""
import json, threading
from engine.feedback import events


def test_concurrent_first_reads_do_not_double(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(20000):
            fh.write(json.dumps({"ts": "2026-11-13T10:00:00", "kind": "application", "status": "SUBMITTED", "i": i}) + "\n")
    monkeypatch.setattr(events, "_path", lambda: str(path))
    events._cache.update(path=None)
    start = threading.Barrier(8)
    counts = []

    def worker():
        start.wait()
        counts.append(len(events.read("application")))

    ts = [threading.Thread(target=worker) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert counts == [20000] * 8
    assert len(events.read()) == 20000
    events._cache.update(path=None)
