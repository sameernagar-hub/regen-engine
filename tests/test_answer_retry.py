"""11-28: answers saved straight to the bank re-open their parked jobs; a 3rd stop is not final once answered."""
import json, os


def test_save_marks_the_job_for_the_answers_container(tmp_path, monkeypatch):
    from engine.feedback import answers as A, answer_queue as Q
    monkeypatch.setattr(A, "record", lambda *a, **k: None)
    prof, ws = tmp_path / "p", tmp_path / "w"
    prof.mkdir(); ws.mkdir()
    A.save("Initech - Software Engineer", "Ideal start date", "Immediately", profile=str(prof), workspace=str(ws), by="shadow")
    files = os.listdir(ws / "answers" / "retry")
    assert len(files) == 1
    assert json.load(open(ws / "answers" / "retry" / files[0]))["job"] == "Initech - Software Engineer"
    monkeypatch.setattr(Q, "QDIR", str(ws / "answers"))
    assert Q._take_retries() == ["Initech - Software Engineer"]
    assert os.listdir(ws / "answers" / "retry") == []          # taken once


def test_retry_skips_walled_and_cooling_ats(tmp_path, monkeypatch):
    from engine.feedback import answer_queue as Q
    from engine import pipeline
    from engine.apply import runner
    entries = {"Globex - SWE": {"name": "Globex - SWE", "url": "https://jobs.ashbyhq.com/globex/1", "resume": "r.pdf"},
               "Initech - SWE": {"name": "Initech - SWE", "url": "https://job-boards.greenhouse.io/initech/jobs/1", "resume": "r.pdf"}}
    monkeypatch.setattr(Q, "find_entry", lambda job: dict(entries[job]))
    monkeypatch.setattr(Q, "BOX", str(tmp_path))
    monkeypatch.setattr(Q, "record", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "latest_status", lambda: {})
    monkeypatch.setattr(pipeline, "history", lambda: (set(), set()))
    monkeypatch.setattr(runner, "ashby_cooling", lambda: True)
    assert Q._retry(["Globex - SWE", "Initech - SWE"]) == 1
    batch = json.load(open(tmp_path / "inbox" / os.listdir(tmp_path / "inbox")[0]))
    assert [b["name"] for b in batch] == ["Initech - SWE"]


def test_third_stop_reopens_only_when_answered_after_it(monkeypatch):
    from engine import pipeline
    u = "https://job-boards.greenhouse.io/initech/jobs/1"
    stop = lambda ts: {"kind": "application", "url": u, "status": "NEEDS YOU", "ts": ts, "detail": "NEEDS YOU: Ideal start date"}
    monkeypatch.setattr(pipeline, "answerable_now", lambda d: True)
    monkeypatch.setattr(pipeline.os.path, "getmtime", lambda p: 1795852800.0)  # bank saved after the stops below
    rows = [stop("2026-11-01T10:00:00")] * 3
    monkeypatch.setattr(pipeline, "read", lambda kind=None: rows)
    assert pipeline.latest_status()[u] == "RETRY"
    rows.append(stop("2026-11-01T11:00:00"))                     # a 4th stop on the same question is final
    assert pipeline.latest_status()[u] == "NEEDS YOU"
    monkeypatch.setattr(pipeline, "answerable_now", lambda d: False)
    assert pipeline.latest_status()[u] == "NEEDS YOU"
