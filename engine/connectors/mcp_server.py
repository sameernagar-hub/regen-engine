"""`python -m engine mcp`: the engine as an MCP server (stdio), for Claude Code, Claude Desktop or any MCP client.

Read-only tools over the engine's memory: what was sent (with proof), what needs the human, outcomes, the knowledge
graph, and the job queue. Nothing here applies, submits or changes files; that stays in the CLI where every
action is logged and guarded by the airbags. Register it with the repo's .mcp.json.
"""
import json, os, re

from mcp.server.mcpserver import MCPServer

from engine.config import WORKSPACE
from engine.memory import graph as G

mcp = MCPServer("regen-engine", version="0.7.0",
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


def main(argv=None):
    mcp.run("stdio")


if __name__ == "__main__":
    main()
