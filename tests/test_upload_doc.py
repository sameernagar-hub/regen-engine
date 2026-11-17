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
