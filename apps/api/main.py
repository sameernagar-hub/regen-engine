"""REGEN API (v0.8): a typed window over the engine's evidence, plus one guarded write (answers).

  uvicorn apps.api.main:app --host 127.0.0.1 --port 8787        (OpenAPI docs at /docs)

Everything is derived from the append-only event log (Postgres or events.jsonl, see store.py) plus files the engine
already wrote (proof screenshots). The only write is POST /api/answers (v0.8, "answer from the page"): enabled only
when REGEN_API_WRITE=1, only from localhost, never for legal / EEO / sensitive questions (engine/feedback/answers.py).
"""
import asyncio, collections, json, os, re, time

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from apps.api import store
from apps.api.models import AnswerIn, AnswerOut, Application, Drafted, Event, HumanItem, Narration, Outcome, Snapshot
from engine.config import WORKSPACE
from engine.feedback import answers as A
from engine.live.server import narrate, who

WRITE = os.environ.get("REGEN_API_WRITE") == "1"
app = FastAPI(title="REGEN API", version="0.8.0",
              description="API over the REGEN job engine's append-only event log (read-only, plus POST /api/answers when enabled).")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("REGEN_WEB_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(","),
                   allow_methods=["GET", "POST"] if WRITE else ["GET"], allow_headers=["*"])

WAITING = ("NEEDS YOU", "FAILED", "FLAGGED")


def _proof(path):
    return path if path and os.path.exists(os.path.join(WORKSPACE, path)) else None


def fold():
    """One pass over the log -> latest application per job, plus resume metadata and outcomes."""
    latest, resumes, outcomes = {}, {}, []
    for _, e in store.read():
        k = e.get("kind")
        if k == "resume" and e.get("job"):
            resumes[e["job"]] = e
        elif k == "application" and not e.get("dry") and e.get("job"):
            latest[e.get("url") or " ".join(e["job"].lower().split())] = e  # by URL: two roles can share a name
        elif k == "outcome":
            outcomes.append(e)
    apps = []
    for e in latest.values():
        r = resumes.get(e["job"], {})
        co, role = who(e["job"])
        apps.append(Application(
            job=e["job"], company=co, role=role, status=(e.get("status") or "?").split(":")[0], ts=e["ts"],
            url=e.get("url"), lane=r.get("lane"), proof=_proof(e.get("proof")), resume=e.get("resume"),
            facts=[f for _, fs in (r.get("facts") or []) for f in fs],
            answers=[(str(q), None if a is None else str(a)) for q, a in (e.get("answers") or []) if isinstance(q, str)],
            detail=e.get("detail")))
    apps.sort(key=lambda a: a.ts, reverse=True)
    return apps, outcomes


@app.get("/api/health")
def health():
    return {"ok": True, "backend": store.backend()}


@app.get("/api/snapshot", response_model=Snapshot)
def snapshot():
    apps, outcomes = fold()
    verified = [a for a in apps if a.status == "SUBMITTED" and a.proof]
    today = time.strftime("%Y-%m-%d")
    boards = 0
    try:
        b = json.load(open(os.path.join(WORKSPACE, "boards.json")))
        boards = sum(len(v) for k, v in b.items() if k != "dead") - len(b.get("dead", []))
    except (OSError, ValueError):
        pass
    seen = os.path.join(WORKSPACE, "seen.json")
    return Snapshot(verified=len(verified), verified_today=sum(a.ts.startswith(today) for a in verified),
                    waiting=sum(a.status in WAITING for a in apps), boards=boards,
                    last_poll=os.path.getmtime(seen) if os.path.exists(seen) else None,
                    by_lane=dict(collections.Counter(a.lane or "earlier" for a in verified)),
                    outcomes=dict(collections.Counter(o.get("outcome") for o in outcomes)), backend=store.backend())


@app.get("/api/applications", response_model=list[Application])
def applications(status: str | None = Query(None, description="SUBMITTED, NEEDS YOU, FAILED, FLAGGED, SKIPPED"),
                 limit: int = Query(200, le=2000)):
    apps, _ = fold()
    return [a for a in apps if not status or a.status == status][:limit]


@app.get("/api/human", response_model=list[HumanItem])
def human():
    apps, _ = fold()
    out = []
    for a in apps:
        if a.status in WAITING:
            n = narrate({"kind": "application", "job": a.job, "status": "NEEDS YOU", "detail": a.detail or ""})
            out.append(HumanItem(job=a.job, status=a.status, text=n["text"] if n else a.job, url=a.url, resume=a.resume,
                                 missing=A.missing_questions(a.detail)))
    return out


@app.post("/api/answers", response_model=AnswerOut)
def answer(body: AnswerIn, request: Request):
    """Answer a waiting question once; the engine reuses it on every form and re-queues the job."""
    if not WRITE:
        raise HTTPException(403, "writes are disabled (set REGEN_API_WRITE=1 on your own machine)")
    if (request.client.host if request.client else "") not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(403, "answers can only be written from this computer")
    try:
        return AnswerOut(**A.save(body.job, body.question, body.answer))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/drafts", response_model=list[Drafted])
def drafts(limit: int = Query(200, le=2000)):
    """Answers the engine drafted from the Fact Bank and sent without waiting, newest first."""
    return [Drafted(**d) for d in A.drafted(limit)]


@app.get("/api/outcomes", response_model=list[Outcome])
def outcomes():
    _, outs = fold()
    return [Outcome(ts=o["ts"], company=o.get("company"), outcome=o.get("outcome", "?"), subject=o.get("subject"),
                    jobs=o.get("jobs") or []) for o in reversed(outs)]


@app.get("/api/events", response_model=list[Event])
def events(after: int = 0, kind: str | None = None, limit: int = Query(200, le=5000)):
    rows = [(i, e) for i, e in store.read(after) if not kind or e.get("kind") == kind]
    return [Event(id=i, ts=e.get("ts", ""), kind=e.get("kind", "?"), job=e.get("job"), status=e.get("status"), data=e)
            for i, e in rows[-limit:]]


@app.get("/api/narration", response_model=list[Narration])
def narration(after: int = 0, limit: int = Query(40, le=500)):
    out = []
    for i, e in store.read(after):
        n = narrate(e)
        if n:
            out.append(Narration(id=i, ts=e.get("ts"), **n))
    return out[-limit:]


@app.get("/api/proof/{name}")
def proof(name: str):
    """A proof screenshot, by file name only (no paths), from workspace/proof."""
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+\.png", name):
        raise HTTPException(400, "bad name")
    p = os.path.join(WORKSPACE, "proof", name)
    if not os.path.exists(p):
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png")


@app.get("/api/stream")
async def stream(after: int = 0):
    """SSE: `narration` for each new event, `snapshot` when anything changes (and every 15 s as a keep-alive)."""
    async def gen():
        last, marker, beat = after, None, 0.0
        while True:
            m = store.size_marker()
            if m != marker:
                marker = m
                for i, e in store.read(last):
                    last = i
                    n = narrate(e)
                    if n:
                        yield f"event: narration\ndata: {Narration(id=i, ts=e.get('ts'), **n).model_dump_json()}\n\n"
                yield f"event: snapshot\ndata: {snapshot().model_dump_json()}\n\n"; beat = time.time()
            elif time.time() - beat > 15:
                yield f"event: snapshot\ndata: {snapshot().model_dump_json()}\n\n"; beat = time.time()
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/graph")
def graph(questions: bool = True):
    """The engine's memory as a graph: You -> lanes -> applications -> companies, facts used, questions answered,
    outcomes, ATS (engine/memory/graph.py; same model as engine/memory/schema.cypher)."""
    from engine.memory import graph as G
    return G.build(questions=questions)
