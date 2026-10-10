"""`python -m engine mcp`: the engine as an MCP server (stdio), for Claude Code, Claude Desktop or any MCP client.

Read tools over the engine's memory: what was sent (with proof), what needs the human, outcomes, the knowledge
graph, the job queue, and live pipeline status. v0.8 adds orchestration: start a pipeline run and deliver Greenhouse
email codes. Those two only work when REGEN_MCP_WRITE=1 is set for the server; the run itself goes through the same
CLI, airbags and event log as a run you start by hand. Register it with the repo's .mcp.json.
"""
import datetime, glob, json, os, re, subprocess, sys

from mcp.server.mcpserver import MCPServer

from engine.config import WORKSPACE
from engine.memory import graph as G

mcp = MCPServer("regen-engine", version="0.10.0",
                instructions="REGEN job engine. Your assistant is the engine's operator at zero cost: read its memory "
                             "(applications with proof, outcomes, knowledge graph, queue, Fact Bank), start/stop runs, "
                             "deliver email codes, record inbox replies, and answer blocking questions. Writes need "
                             "REGEN_MCP_WRITE=1. Never invent facts: answers come from the user or the Fact Bank.")


def _api():
    from apps.api import main as api  # same derivations as the web app, one source of truth
    return api


@mcp.tool(description="Proof-backed counts: verified applications (total/today), items waiting on the human, boards watched, outcomes.")
def engine_status() -> dict:
    return _api().snapshot().model_dump()


@mcp.tool(description="Applications, newest first. status: SUBMITTED, NEEDS YOU, FAILED, FLAGGED or SKIPPED (empty = all).")
def applications(status: str = "", limit: int = 50) -> list[dict]:
    return [a.model_dump() for a in _api().applications(status or None, min(limit, 500))]


@mcp.tool(description="What only the human can do right now (each job's latest state): personal questions, bot checks, missing answers.")
def human_queue() -> list[dict]:
    return [h.model_dump() for h in _api().human()]


@mcp.tool(description="Inbox outcomes the engine classified (confirmation, rejection, oa, interview, offer, scam), newest first.")
def outcomes(limit: int = 30) -> list[dict]:
    return [o.model_dump() for o in _api().outcomes()][:limit]


@mcp.tool(description="Knowledge-graph lookup. Pass a company name, a Fact Bank id (e.g. 's_rag') or a lane ('backend'). "
                      "Returns the node and everything connected to it (applications, facts used, questions answered, outcomes).")
def memory_query(term: str) -> dict:
    g = G.build()
    t = term.strip().lower()
    hit = next((n for n in g["nodes"] if n["id"].lower() in (t, "co:" + t, "fact:" + t, "lane:" + t)), None) \
        or next((n for n in g["nodes"] if t in n["label"].lower()), None)
    return G.neighbors(hit["id"], g) if hit else {"node": None, "neighbors": [], "edges": []}


@mcp.tool(description="Jobs discovered and waiting in the queue (not yet applied), optionally filtered by a word in company/title.")
def job_queue(contains: str = "", limit: int = 40) -> list[dict]:
    p = os.path.join(WORKSPACE, "queue.json")
    q = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []
    rx = re.compile(re.escape(contains), re.I) if contains else None
    keep = ("id", "ats", "company", "title", "location", "posted", "url", "source")
    return [{k: j.get(k) for k in keep} for j in q if not rx or rx.search(f"{j.get('company')} {j.get('title')}")][:limit]


WRITE = os.environ.get("REGEN_MCP_WRITE") == "1"


@mcp.tool(description="Live pipeline status: each applier log's last results, jobs waiting for a Greenhouse email code, "
                      "and today's verified count.")
def pipeline_status(tail: int = 8) -> dict:
    logs = sorted(glob.glob(os.path.join(WORKSPACE, "logs", "apply_*.log")) + glob.glob(os.path.join(WORKSPACE, "logs", "run_*.log")),
                  key=os.path.getmtime, reverse=True)[:4]
    out = {}
    for p in logs:
        lines = [l.rstrip() for l in open(p, encoding="utf-8", errors="replace") if "] -> " in l or "jobs in" in l]
        out[os.path.basename(p)] = lines[-tail:]
    from engine.apply.codes import waiting
    return {"appliers": out, "waiting_for_code": [s for s, _ in waiting()], "verified_today": _api().snapshot().verified_today}


@mcp.tool(description="Start the whole pipeline in the background (discover, select, build, apply, report). "
                      "Needs REGEN_MCP_WRITE=1. Returns the log path; watch it with pipeline_status.")
def pipeline_run(days: int = 1, max_jobs: int = 30, appliers: int = 2, tabs: int = 3, scan: bool = True) -> dict:
    if not WRITE:
        return {"error": "writes are disabled for this MCP server (set REGEN_MCP_WRITE=1)"}
    from engine.config import ROOT
    name = "pipeline_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"
    log = open(os.path.join(WORKSPACE, "logs", name), "w", encoding="utf-8")
    args = [sys.executable, "-m", "engine", "run", "--days", str(days), "--max", str(max_jobs),
            "--appliers", str(appliers), "--tabs", str(tabs)] + ([] if scan else ["--no-scan"])
    p = subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    return {"started": True, "pid": p.pid, "log": f"workspace/logs/{name}"}


@mcp.tool(description="Deliver Greenhouse security codes read from the inbox: codes = [{company, code, when}]. A code only "
                      "goes to the waiting job whose company the email names, and only if it was sent after the job "
                      "started waiting. Needs REGEN_MCP_WRITE=1.")
def submit_codes(codes: list[dict]) -> dict:
    if not WRITE:
        return {"error": "writes are disabled for this MCP server (set REGEN_MCP_WRITE=1)"}
    from engine.apply.codes import match, waiting
    return {"written": match(codes), "still_waiting": [s for s, _ in waiting()]}


# ---- v0.10: the zero-cost cord. Everything the control room can do, the user's own AI client can do over MCP. ----

@mcp.tool(description="Start a run the way the control room does: {days, max, appliers, tabs, cap, loop (minutes, 0 = one "
                      "pass), scan, newgrad, feed, ats: [greenhouse, lever, ashby, workable], dry}. Needs REGEN_MCP_WRITE=1.")
def run_start(params: dict) -> dict:
    if not WRITE:
        return {"error": "writes are disabled for this MCP server (set REGEN_MCP_WRITE=1)"}
    from engine import control as C
    try:
        return C.start(params)
    except RuntimeError as e:
        return {"error": str(e)}


@mcp.tool(description="Stop the run started by run_start / the control room (kills its process tree). Needs REGEN_MCP_WRITE=1.")
def run_stop() -> dict:
    if not WRITE:
        return {"error": "writes are disabled for this MCP server (set REGEN_MCP_WRITE=1)"}
    from engine import control as C
    return C.stop()


@mcp.tool(description="Live control-room state: the current run's steps, each active applier's tabs (job + state), latest "
                      "answers, queue size by ATS, and when Ashby reopens.")
def control_state() -> dict:
    from apps.api import control
    return control.state()


@mcp.tool(description="Title/company filters (regex alternations) and the years-of-experience gate from presets.")
def filters_get() -> dict:
    from apps.api import control
    return control.filters()


@mcp.tool(description="Replace include_titles / exclude_titles / exclude_companies (regex; each must compile; old file kept "
                      "as .bak-ui). Needs REGEN_MCP_WRITE=1.")
def filters_set(include_titles: str = "", exclude_titles: str = "", exclude_companies: str = "") -> dict:
    if not WRITE:
        return {"error": "writes are disabled for this MCP server (set REGEN_MCP_WRITE=1)"}
    import json as _j, re as _re, shutil
    from engine.config import profile_file
    path = profile_file("domains.json")
    cur = _j.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for k, v in (("include_titles", include_titles), ("exclude_titles", exclude_titles), ("exclude_companies", exclude_companies)):
        if v:
            _re.compile(v, _re.I)
            cur[k] = v
    if os.path.exists(path):
        shutil.copy(path, path + ".bak-ui")
    _j.dump(cur, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return filters_get()


@mcp.tool(description="The Fact Bank: every fact with how many resumes used it and in which lanes, plus roles, projects, "
                      "skills, education and where each fact came from. The only source the engine writes from.")
def factbank() -> dict:
    from apps.api import control
    return control.factbank()


@mcp.tool(description="Trust gate for one posting: is the application host an employer-controlled ATS, and does the "
                      "description carry job-scam red flags? Returns {ok, reasons}.")
def trust_check(url: str, description: str = "") -> dict:
    from engine.discovery.trust import verdict
    ok, reasons = verdict(url, description)
    return {"ok": ok, "reasons": reasons}


@mcp.tool(description="Why the queue is ordered the way it is: the top N jobs with their priority score and its parts "
                      "(level, lane, freshness, employer tier, sponsor, learned reply rate).")
def priority_explain(top: int = 20) -> list[dict]:
    import json as _j
    from engine.discovery.priority import lane_rates, score
    q = _j.load(open(os.path.join(WORKSPACE, "queue.json"), encoding="utf-8"))
    rates = lane_rates()
    rows = [(score(j, rates), j) for j in q]
    rows.sort(key=lambda r: -r[0][0])
    return [{"company": j["company"], "title": j["title"], "score": s, "parts": parts, "url": j["url"]} for (s, parts), j in rows[:top]]


@mcp.tool(description="What's waiting on the user, grouped by blocking question (answer one question to unblock many jobs).")
def needs_by_question() -> list[dict]:
    from engine.feedback.answers import LEGAL_OR_SENSITIVE
    groups = {}
    for it in _api().human():
        for q in (it.missing or [it.text]):
            groups.setdefault(q, []).append(it.job)
    return sorted(({"question": q, "jobs": js, "count": len(js), "user_only": bool(LEGAL_OR_SENSITIVE.search(q))}
                   for q, js in groups.items()), key=lambda g: (g["user_only"], -g["count"]))


@mcp.tool(description="Save the user's answer to a blocking question (reused on every form that asks it; legal / EEO / "
                      "sponsorship questions are refused: those come from presets only). Needs REGEN_MCP_WRITE=1.")
def answer_save(job: str, question: str, answer: str) -> dict:
    if not WRITE:
        return {"error": "writes are disabled for this MCP server (set REGEN_MCP_WRITE=1)"}
    from engine.feedback import answers as A
    try:
        return A.save(job, question, answer)
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool(description="Record recruiting emails the assistant read from the user's inbox: messages = [{date, from, subject, "
                      "snippet}]. Classifies confirmation / rejection / OA / interview / offer / scam and links them to "
                      "applications. Needs REGEN_MCP_WRITE=1.")
def inbox_record(messages: list[dict]) -> dict:
    if not WRITE:
        return {"error": "writes are disabled for this MCP server (set REGEN_MCP_WRITE=1)"}
    from engine.feedback import inbox
    evs = inbox.ingest(messages)
    return {"recorded": [{"outcome": e.get("outcome"), "company": e.get("company")} for e in (evs or [])]}



@mcp.tool(description="Outreach drafts for recent submissions at tier companies and startups: subject, body (template "
                      "lines + Fact Bank entries that application's resume used), and a Gmail compose link. Nothing is "
                      "sent; the user adds the recipient. rebuild=True regenerates them (needs REGEN_MCP_WRITE=1).")
def outreach_drafts(days: int = 7, rebuild: bool = False) -> list[dict]:
    from engine import outreach as O
    if rebuild:
        if not WRITE:
            return [{"error": "writes are disabled for this MCP server (set REGEN_MCP_WRITE=1)"}]
        return O.build(days)
    path = os.path.join(WORKSPACE, "outreach", "drafts.json")
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []


def main(argv=None):
    mcp.run("stdio")


if __name__ == "__main__":
    main()
