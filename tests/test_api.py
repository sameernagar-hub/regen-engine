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
    monkeypatch.setattr(M, "ANSWERS", False)
    r = client.post("/api/answers", json={"job": "Globex - AI Engineer", "question": "Are you open to travel?", "answer": "Yes"})
    assert r.status_code == 403


def test_answer_saved_logged_and_requeued(monkeypatch, tmp_path, seeded):
    monkeypatch.setattr(M, "WRITE", True); monkeypatch.setattr(M, "ANSWERS", True); monkeypatch.setattr(M, "QUEUE", False)
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
    monkeypatch.setattr(M, "WRITE", True); monkeypatch.setattr(M, "ANSWERS", True); monkeypatch.setattr(M, "QUEUE", False)
    r = client.post("/api/answers", json={"job": "Globex - AI Engineer", "question": q, "answer": "x"})
    assert r.status_code == 422


def test_answer_validation(monkeypatch):
    monkeypatch.setattr(M, "WRITE", True); monkeypatch.setattr(M, "ANSWERS", True); monkeypatch.setattr(M, "QUEUE", False)
    assert client.post("/api/answers", json={"job": "J", "question": "Why us?", "answer": "  "}).status_code == 422
    assert client.post("/api/answers", json={"job": "J", "question": "Why us?", "answer": "x" * 2001}).status_code == 422
    assert A.requeue("Nobody - Nothing") is False


def test_missing_questions_parser():
    assert A.missing_questions("NEEDS YOU: A? | B?") == ["A?", "B?"]
    assert A.missing_questions("NEEDS YOU: no adapter for workday yet; resume ready") == []
    assert A.missing_questions("SUBMITTED") == [] and A.missing_questions(None) == []


def test_dsn_from_secret_file(tmp_path, monkeypatch):
    pw = tmp_path / "pg"
    pw.write_text("a/b c\n")
    monkeypatch.delenv("REGEN_DATABASE_URL", raising=False)
    monkeypatch.setenv("REGEN_DB_HOST", "postgres")
    monkeypatch.setenv("REGEN_DB_PASSWORD_FILE", str(pw))
    assert store._dsn() == "postgresql://regen:a%2Fb%20c@postgres:5432/regen"
    monkeypatch.setenv("REGEN_DB_PASSWORD_FILE", str(tmp_path / "missing"))
    assert store._dsn() is None
    monkeypatch.setenv("REGEN_DATABASE_URL", "postgresql://x")
    assert store._dsn() == "postgresql://x"


def test_migrate_reads_only_whole_new_lines(tmp_path, monkeypatch):
    from apps.api import migrate as MG

    class Con:
        rows = []
        def cursor(self):
            return self
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def execute(self, sql, row):
            self.rows.append(row)
            self.rowcount = 1

    log = tmp_path / "events.jsonl"
    log.write_bytes(b'{"kind": "code", "slug": "a"}\nnot json\n{"kind": "app')
    monkeypatch.setattr(MG, "EVENTS", str(log))
    con = Con()
    added, off = MG.copy_events(con, 0)
    assert added == 1 and con.rows[0][2] == "code" and con.rows[0][4] == 1
    assert off == len(b'{"kind": "code", "slug": "a"}\nnot json\n')  # partial line waits for the next pass
    with open(log, "ab") as fh:
        fh.write(b'lication", "v": 2}\n')
    added, off = MG.copy_events(con, off)
    assert added == 1 and con.rows[-1][2] == "application" and con.rows[-1][4] == 2
    assert off == log.stat().st_size


def test_stream_after_huge_means_from_now(monkeypatch):
    """Clients open /api/stream?after=999999999 for "only new events"; the server must clamp it, or nothing streams."""
    import asyncio
    from engine.feedback import events
    resp = asyncio.run(M.stream(after=999999999))
    it = resp.body_iterator

    async def first_two():
        a = await it.__anext__()
        events.record("discovered", job="Initech - Platform Engineer", url="https://job-boards.greenhouse.io/initech/jobs/9",
                      ats="greenhouse", lag_min=2)
        out = [a]
        while "narration" not in out[-1]:
            out.append(await it.__anext__())
        return out
    out = asyncio.run(asyncio.wait_for(first_two(), 20))
    assert out[0].startswith("event: snapshot") and "Platform Engineer" in out[-1]


def test_answer_queue_end_to_end(monkeypatch, tmp_path, seeded):
    """Bank mode: /needs answer -> answers/inbox -> the answers container saves it and drops ONE retry batch in
    batches/inbox (found in batches/done, where container batches end up); submitted jobs are not retried."""
    from engine.feedback import answer_queue as Q
    from engine import pipeline
    for k, v in (("QDIR", seeded / "answers"), ("BOX", seeded / "batches"), ("WORKSPACE", seeded)):
        monkeypatch.setattr(Q, k, str(v))
    monkeypatch.setattr(pipeline, "read", events.read)
    monkeypatch.setattr(M, "ANSWERS", True); monkeypatch.setattr(M, "QUEUE", True)
    (seeded / "batches" / "done").mkdir(parents=True, exist_ok=True)
    (seeded / "batches" / "done" / "run_x_0.json").write_text(json.dumps(
        [{"name": "Globex - AI Engineer", "url": "https://jobs.ashbyhq.com/globex/2", "resume": "out/r.pdf", "_answers": []}]))
    r = client.post("/api/answers", json={"job": "Globex - AI Engineer", "question": "Are you open to travel?", "answer": "Yes"})
    assert r.status_code == 200 and r.json()["source"].startswith("queued")
    assert not (tmp_path / "answers.json").exists()  # nothing written by the API itself
    assert client.post("/api/answers", json={"job": "J", "question": "What is your gender?", "answer": "x"}).status_code == 422
    out = Q.drain()
    assert out == {"saved": 1, "refused": 0, "retry": 1}
    assert json.load(open(tmp_path / "answers.json", encoding="utf-8"))[0]["answer"] == "Yes"
    batch = [f for f in os.listdir(seeded / "batches" / "inbox") if f.startswith("answers_")]
    assert len(batch) == 1 and json.load(open(seeded / "batches" / "inbox" / batch[0])) == [
        {"name": "Globex - AI Engineer", "url": "https://jobs.ashbyhq.com/globex/2", "resume": "out/r.pdf"}]
    assert Q.drain() == {"saved": 0, "refused": 0, "retry": 0}  # drained once, never twice
    (seeded / "KILL").write_text("x")
    client.post("/api/answers", json={"job": "Globex - AI Engineer", "question": "Why us?", "answer": "Because."})
    assert Q.drain() == {"held": True} and len(os.listdir(seeded / "answers" / "inbox")) == 1


def test_explorer_page_tracker_and_rows():
    """The API's own page (/) and its jsonl fallback: tables, filtered rows, CSV download, request tracker."""
    assert "Ledger database" in client.get("/").text and client.get("/db").status_code == 200
    t = client.get("/api/db/tables").json()
    assert t[0]["name"] == "events" and t[0]["rows"] >= 3
    rows = client.get("/api/db/rows/events?q=globex").json()
    assert rows and all("globex" in json.dumps(r).lower() for r in rows)
    csv_ = client.get("/api/db/rows/events?format=csv")
    assert csv_.headers["content-type"].startswith("text/csv") and "attachment" in csv_.headers["content-disposition"]
    assert client.get("/api/db/rows/pg_shadow").status_code == 404  # allowlist only
    assert any(r["route"] == "GET /api/db/rows/{name}" for r in client.get("/api/track").json())


def test_mcp_in_bank_levels(monkeypatch, seeded):
    """The bank's MCP endpoint: fleet verbs run in-process (kill writes the kill files), ledger rows go through the
    same allowlist as /db, answers need REGEN_MCP_WRITE."""
    from engine.connectors import mcp_server as S
    from engine import supervisor as Sup
    monkeypatch.setattr(S, "IN_BANK", True)
    monkeypatch.setattr(Sup, "WORKSPACE", str(seeded))
    monkeypatch.setattr(Sup, "audit", lambda *a, **k: None)
    assert S.kill("test reason") == {"killed": True} and (seeded / "KILL").read_text().strip().endswith("test reason")
    assert S.ledger_rows("events", q="globex") and S.ledger_rows("pg_shadow")[0]["error"] == "unknown relation"
    monkeypatch.setattr(S, "WRITE", False)
    assert "error" in S.answer_queue_add("J", "Why us?", "Because.")


def test_typed_legal_answer_stays_on_its_job(monkeypatch, tmp_path, seeded):
    """10-15: the user's own arbitration / authorization answer on /needs was refused (422). Now it is accepted, kept
    on that job only (answers/job_extra.json -> the retry batch's extra), never written to answers.json."""
    from engine.feedback import answer_queue as Q
    from engine import pipeline
    for k, v in (("QDIR", seeded / "answers"), ("BOX", seeded / "batches"), ("WORKSPACE", seeded)):
        monkeypatch.setattr(Q, k, str(v))
    monkeypatch.setattr(pipeline, "read", events.read)
    monkeypatch.setattr(M, "ANSWERS", True); monkeypatch.setattr(M, "QUEUE", True)
    (seeded / "batches" / "done").mkdir(parents=True, exist_ok=True)
    (seeded / "batches" / "done" / "run_y_0.json").write_text(json.dumps(
        [{"name": "Initech - SWE", "url": "https://job-boards.greenhouse.io/initech/jobs/99", "resume": "out/r.pdf"}]))
    q = "Please review and acknowledge Initech's Candidate Arbitration Agreement"
    assert client.post("/api/answers", json={"job": "Initech - SWE", "question": q, "answer": "I acknowledge"}).status_code == 200
    assert Q.drain() == {"saved": 1, "refused": 0, "retry": 1}
    assert not (tmp_path / "answers.json").exists()
    batch = [f for f in os.listdir(seeded / "batches" / "inbox") if f.startswith("answers_")][0]
    extra = json.load(open(seeded / "batches" / "inbox" / batch))[0]["extra"]
    from engine.apply.runner import answer_for
    assert answer_for(q, extra) == "I acknowledge" and answer_for(q, {}) != "I acknowledge"
