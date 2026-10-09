# Platform

The engine is CLI-first, and the platform puts typed interfaces on top of the same event log: a REST API for apps,
a live web view for people and an MCP server for agents.

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI + Pydantic (`apps/api`), SSE for live events |
| Web | Next.js + React + TypeScript (`apps/web`), typed client generated from the OpenAPI schema |
| Store | `events.jsonl` (source of truth), optional Postgres mirror (`REGEN_DATABASE_URL`) |
| Agents | MCP server over stdio (`python -m engine mcp`, `.mcp.json`) |
| Public face | anonymized replay (`engine site`) on GitHub Pages and a Render web service |

## REST API (`apps/api`)

| Endpoint | Returns |
|---|---|
| `GET /api/health` | liveness |
| `GET /api/snapshot` | counts: verified total/today, waiting on you, boards, outcomes |
| `GET /api/events` · `GET /api/stream` | raw events · server-sent live stream |
| `GET /api/applications` | latest state per application |
| `GET /api/human` | the human queue: exactly what only you can do |
| `GET /api/outcomes` · `GET /api/drafts` | classified replies · drafted answers for review |
| `GET /api/graph` | knowledge-graph neighborhood |
| `GET /api/stations` | per-stage (listen, judge, write, apply, hear back) live state for the engine room |
| `GET /api/job?u=` | one job's full timeline: facts, coverage, ATS score, Q&A, proof |
| `GET /api/proof/{name}` | a proof screenshot |
| `GET /api/narration` | plain-language narration of recent activity |
| `POST /api/answers` | answer a human-queue question from the page (opt-in `REGEN_API_WRITE=1`, localhost only) |

`REGEN_MODE=public` serves only the anonymized feed (company names hidden), which is how the public demo runs.

## Web app (`apps/web`)

| Route | What you see |
|---|---|
| `/` | live view: work flowing through the five stages, a gold bead per verified application, grouped by lane |
| `/graph` | layered, expanding memory graph |
| `/room` | the engine room: five live rooms (SSE) |
| `/room/[stage]` | one room's live log, with doors to the linked rooms |
| `/job?u=` | the end-to-end timeline of one application |

## MCP server (`engine/connectors/mcp_server.py`)

Read tools: proof-backed **status**, **applications** (by status), **human_queue**, **outcomes**,
**graph lookup**, **queue search**, **pipeline_status**. Write tools behind `REGEN_MCP_WRITE=1`:
**pipeline_run** (start the whole pipeline in the background) and **submit_codes** (deliver email codes). Any MCP
client can ask "what's waiting on me?" or "start a run".

## Deploy

- Local: `python -m engine live` (read-only page) or API + web via `.claude/launch.json`.
- Public: `engine site` builds the anonymized replay; GitHub Pages and Render serve it. The engine never schedules
  itself; the public feed updates when you publish.

Related: [Architecture](Architecture.md) · [Outcomes and learning](Outcomes-and-Learning.md) · [Configuration](Configuration.md)
