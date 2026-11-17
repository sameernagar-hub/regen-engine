import os
from engine.apply import runner


def test_upload_doc_picks_transcript(tmp_path, monkeypatch):
    d = tmp_path / "docs"; d.mkdir()
    (d / "transcript_undergrad.pdf").write_bytes(b"%PDF")
    (d / "transcript_graduate.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr("engine.config.PROFILE", str(tmp_path))
    assert runner.upload_doc("Undergraduate Transcript").endswith("transcript_undergrad.pdf")
    assert runner.upload_doc("Bachelor's transcript").endswith("transcript_undergrad.pdf")
    assert runner.upload_doc("Graduate Transcript").endswith("transcript_graduate.pdf")
    assert runner.upload_doc("Transcript").endswith("transcript_graduate.pdf")
    assert runner.upload_doc("Portfolio") is None


def test_upload_doc_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("engine.config.PROFILE", str(tmp_path))
    assert runner.upload_doc("Undergraduate Transcript") is None


def test_date_answer_start_date():
    import datetime as dt
    t = dt.date(2026, 11, 16)
    assert runner.date_answer("When can you start a new role?", "Immediately (2 weeks notice)", t) == "11/30/2026"
    assert runner.date_answer("Earliest available start date", "3 weeks", t) == "12/07/2026"
    assert runner.date_answer("When can you start?", "1/5/2027", t) == "01/05/2027"
    assert runner.date_answer("Date of birth", "Immediately", t) is None
    assert runner.date_answer("When can you start?", "Not sure", t) is None
