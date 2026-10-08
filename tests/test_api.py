"""API (apps/api) end to end with FastAPI's TestClient over a seeded, throwaway event log."""
import json, os

import pytest
from fastapi.testclient import TestClient

from apps.api import main as M, store
from engine.config import WORKSPACE
from engine.feedback import answers as A, events


@pytest.fixture(autouse=True)
def seeded(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    (ws / "proof").mkdir(parents=True)
    (ws / "batches").mkdir()
    (ws / "proof" / "ok.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    for mod in (events, A):
        monkeypatch.setattr(mod, "WORKSPACE", str(ws))
    monkeypatch.setattr(store, "EVENTS", str(ws / "events.jsonl"))
    monkeypatch.setattr(M, "WORKSPACE", str(ws))
    monkeypatch.setattr(A, "PROFILE", str(tmp_path))
    events._cache.update(path=None)
    rec = events.record
    rec("resume", job="Initech - Backend Engineer", lane="backend", facts=[["acme", ["x_api"]]])
    rec("application", job="Initech - Backend Engineer", url="https://job-boards.greenhouse.io/initech/jobs/1",
        status="SUBMITTED", detail="SUBMITTED", proof="proof/ok.png", answers=[["Why us?", "Because."]], dry=False,
        drafted=[["Why us?", "Because.", ["x_api"]]])
    rec("application", job="Globex - AI Engineer", url="https://jobs.ashbyhq.com/globex/2", status="NEEDS YOU",
        detail="NEEDS YOU: What excites you about Globex? | Are you open to travel?", dry=False)
    rec("outcome", msg_id="m1", outcome="confirmation", company="Initech", subject="Thanks", jobs=["Initech - Backend Engineer"])
    json.dump([{"name": "Globex - AI Engineer", "url": "https://jobs.ashbyhq.com/globex/2", "resume": "out/r.pdf", "_answers": []}],
              open(ws / "batches" / "b1.json", "w"))
    yield ws
    events._cache.update(path=None)


client = TestClient(M.app)


def test_read_endpoints():
    assert client.get("/api/health").json() == {"ok": True, "backend": "jsonl"}
    snap = client.get("/api/snapshot").json()
    assert snap["verified"] == 1 and snap["waiting"] == 1 and snap["outcomes"] == {"confirmation": 1}
    apps = client.get("/api/applications").json()
    assert {a["status"] for a in apps} == {"SUBMITTED", "NEEDS YOU"}
    assert client.get("/api/applications", params={"status": "SUBMITTED"}).json()[0]["facts"] == ["x_api"]
    assert client.get("/api/outcomes").json()[0]["company"] == "Initech"
    assert len(client.get("/api/events").json()) == 4
    assert client.get("/api/events", params={"kind": "outcome"}).json()[0]["kind"] == "outcome"
    assert isinstance(client.get("/api/narration").json(), list)
    g = client.get("/api/graph").json()
    assert any(n["type"] == "Application" for n in g["nodes"])


def test_human_lists_missing_questions():
    h = client.get("/api/human").json()
    assert h[0]["missing"] == ["What excites you about Globex?", "Are you open to travel?"]


def test_proof_paths_are_locked_down():
    assert client.get("/api/proof/ok.png").status_code == 200
    assert client.get("/api/proof/missing.png").status_code == 404
    assert client.get("/api/proof/..%5Cevents.png").status_code == 400


def test_drafts_endpoint():
    d = client.get("/api/drafts").json()
    assert d == [{"ts": d[0]["ts"], "job": "Initech - Backend Engineer", "status": "SUBMITTED", "question": "Why us?",
                  "answer": "Because.", "facts": ["x_api"]}]


def test_answers_write_is_off_by_default(monkeypatch):
    monkeypatch.setattr(M, "WRITE", False)
    r = client.post("/api/answers", json={"job": "Globex - AI Engineer", "question": "Are you open to travel?", "answer": "Yes"})
    assert r.status_code == 403


def test_answer_saved_logged_and_requeued(monkeypatch, tmp_path, seeded):
    monkeypatch.setattr(M, "WRITE", True)
    r = client.post("/api/answers", json={"job": "Globex - AI Engineer", "question": "Are you open to travel?", "answer": "Yes"})
    assert r.status_code == 200 and r.json()["answer"] == "Yes"
    bank = json.load(open(tmp_path / "answers.json", encoding="utf-8"))
    assert bank[0]["pattern"] == A.pattern_for("Are you open to travel?") and "web app" in bank[0]["source"]
    import re
    assert re.search(bank[0]["pattern"], "are you  open to travel?".replace("  ", " "))
    rq = json.load(open(seeded / "batches" / "requeue.json"))
    assert rq == [{"name": "Globex - AI Engineer", "url": "https://jobs.ashbyhq.com/globex/2", "resume": "out/r.pdf"}]
    assert events.read("answer")[-1]["question"] == "Are you open to travel?"
    # same question again replaces, never duplicates; requeue stays deduped
    client.post("/api/answers", json={"job": "Globex - AI Engineer", "question": "Are you open to travel?", "answer": "No"})
    assert [b["answer"] for b in json.load(open(tmp_path / "answers.json", encoding="utf-8"))] == ["No"]
    assert len(json.load(open(seeded / "batches" / "requeue.json"))) == 1


@pytest.mark.parametrize("q", ["Will you require visa sponsorship?", "What is your gender?", "Do you agree to arbitration?",
                               "What is your desired salary?", "Social security number"])
def test_legal_and_sensitive_questions_are_refused(monkeypatch, q):
    monkeypatch.setattr(M, "WRITE", True)
    r = client.post("/api/answers", json={"job": "Globex - AI Engineer", "question": q, "answer": "x"})
    assert r.status_code == 422


def test_answer_validation(monkeypatch):
    monkeypatch.setattr(M, "WRITE", True)
    assert client.post("/api/answers", json={"job": "J", "question": "Why us?", "answer": "  "}).status_code == 422
    assert client.post("/api/answers", json={"job": "J", "question": "Why us?", "answer": "x" * 2001}).status_code == 422
    assert A.requeue("Nobody - Nothing") is False


def test_missing_questions_parser():
    assert A.missing_questions("NEEDS YOU: A? | B?") == ["A?", "B?"]
    assert A.missing_questions("NEEDS YOU: no adapter for workday yet; resume ready") == []
    assert A.missing_questions("SUBMITTED") == [] and A.missing_questions(None) == []
