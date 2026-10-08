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

mcp = MCPServer("regen-engine", version="0.8.0",
                instructions="Read-only memory of the REGEN job engine: applications with proof, what's waiting on "
                             "the human, outcomes, the knowledge graph, and the job queue.")


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


def main(argv=None):
    mcp.run("stdio")


if __name__ == "__main__":
    main()
