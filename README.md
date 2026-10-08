<div align="center">

# REGEN

### An open-source job engine that finds roles minutes after they're posted, writes a resume for each one from facts you can prove, applies at the company's own site, and shows you the evidence.

[![ci](https://github.com/sameernagar-hub/regen-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/sameernagar-hub/regen-engine/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-informational)](pyproject.toml)
[![next.js](https://img.shields.io/badge/web-Next.js%20%2B%20TypeScript-black)](apps/web)
[![fastapi](https://img.shields.io/badge/api-FastAPI%20%2B%20Pydantic-009688)](apps/api)
[![mcp](https://img.shields.io/badge/MCP-server-8a63d2)](engine/connectors/mcp_server.py)
[![privacy](https://img.shields.io/badge/privacy-gated%20in%20CI-success)](SECURITY.md)

<img src="docs/assets/live-dark.png" alt="REGEN live view: work moves through listening, judging, writing, applying and hearing back; each gold bead is an application sent with proof, grouped by resume lane" width="100%">

<sub>The live view replaying real activity, company names hidden. Each gold bead is an application with a saved confirmation page, grouped by the resume lane that wrote it.</sub>

**[Live demo](https://sameernagar-hub.github.io/regen-engine/)** · **[In plain English](#in-plain-english)** · **[Features](#features)** · **[Quick start](#quick-start)** · **[Architecture](#architecture)** · **[Platform](#the-platform-v07)** · **[Roadmap](#roadmap)**

</div>

---

## In plain English

Looking for a job usually goes like this: a company posts a role on its own careers page, it shows up on LinkedIn a day or two later, and by then hundreds of people have applied. Most of them sent the same resume to every job.

REGEN does the opposite, and it does it on your own computer:

1. **It watches the source.** It checks the careers pages of about 2,100 companies directly, every few minutes, and notices new roles soon after they go up. It also reads the job alerts already landing in your inbox and traces each one back to the company's own page.
2. **It decides honestly.** Before spending any effort, it reads the job description and skips roles you can't get: ones that need citizenship or a clearance, refuse visa sponsorship, want more years than you have, or are built on a language you don't list.
3. **It writes one resume per job, from your facts only.** You keep a "Fact Bank": every true line about your work, each with an id. For each job, REGEN picks and orders the lines that match what the job asks for. It cannot write a new claim; a checker rejects anything that isn't in your Fact Bank.
4. **It fills in the application.** It opens the company's form, uploads that job's resume and answers each question. Legal and personal questions (work authorization, sponsorship, citizenship) are answered only from what you saved. Open questions ("Why us?") get answers built from your Fact Bank, and every one is logged. An "are you human?" check always comes to you.
5. **It keeps the receipt.** Every submission saves a screenshot of the company's "thank you" page. The count you see only includes applications with a receipt.
6. **It listens for replies.** It reads your inbox for confirmations, rejections, assessments and interviews, links each one back to the application and the resume that earned it, and learns which approach works.

You watch all of this on one live page, and you can open any application to see exactly which facts its resume used and every question it answered.

Job hunting is an old problem. This project keeps trying new approaches to it, and each one ships only when it can be checked: a test, a log line, or a receipt.

---

## Features

Everything below is shipped and lives in this repository. Paths point to the code.

### 1. Discovery: find roles at the source
| Feature | What it does | Code |
|---|---|---|
| Four ATS APIs | Reads public job boards on **Greenhouse, Ashby, Lever and Workable** in parallel and normalizes them into one queue. | `engine/discovery/ats.py`, `scan.py` |
| Board registry | **2,363 company boards** registered, dead ones (currently 259) skipped automatically; grows daily by harvesting public GitHub job lists. | `python -m engine boards harvest` |
| Always-on watcher | Polls every board on an interval and announces only brand-new postings, with the minutes since they went live. Runs as a small Docker service. | `engine/discovery/watch.py`, `deploy/watcher.compose.yml` |
| Job-alert emails | Reads LinkedIn, Indeed, Glassdoor, ZipRecruiter and Handshake alert emails inside your signed-in Gmail tab (no API key; only title, company and location are extracted) and resolves each listing to the employer's own board. First run: 146 listings → 30 found at the source. | `engine/discovery/gmail_alerts.js`, `alerts.py` |
| GitHub job lists | Pulls the SimplifyJobs new-grad list and adds its Greenhouse, Ashby, Lever and Workable postings to the queue. | `python -m engine feed 3 --queue` |
| Lead resolution | Turns aggregator leads (newgrad-jobs.com, alert emails) into the real posting by matching the company's own ATS board and the job title; results are cached. | `engine/discovery/newgrad.py` |
| Domain filter | Your target titles, seniority, excluded employers and US-only rules, with location checks that catch "Remote" roles whose title names a non-US city. | `engine/discovery/filters.py`, `profile/domains.json` |

### 2. Fit gate: don't apply where you'll be screened out
| Check | Example it blocks |
|---|---|
| Citizenship / ITAR / export control | "Must be a U.S. citizen" |
| Security clearance | "Active secret clearance required" |
| No sponsorship | "We are unable to sponsor visas" |
| Graduation window | "Graduating spring 2027" |
| Years of experience | Any minimum above **your** number from presets (added after two "4+ years" applications were rejected within two days) |
| Core stack | A *required* language you don't list ("Strong C# required"), matched as a whole word so "trust" never reads as "Rust" |

Every skip is logged with its reason and never re-queued. Code: `engine/tailoring/tailor.py` (`fit`).

### 3. Tailoring: one truthful resume per job
- **Fact Bank only.** Resumes are assembled from `profile/fact_bank.json`. `resume.validate()` rejects any role, fact, project or skill that isn't there.
- **Per-job selection and order.** Each job is routed to a lane (backend, full-stack, AI, data, platform) and its facts are ranked by how many of the job's technologies they mention.
- **The job's own wording.** When a job spells a skill you have differently (Postgres, RESTful, Golang, K8s), the skills line shows both, e.g. `PostgreSQL (Postgres)`, so keyword screens match. The validator only accepts a changed line if removing those aliases gives back the original exactly.
- **No repeats.** Versions of the same accomplishment are grouped, and a resume uses at most one from each group.
- **Audit trail.** Every resume event records the fact ids it used and which job terms it covers or misses. Always one page.

Code: `engine/tailoring/` · Tests: `tests/test_core.py`

### 4. Apply: fill forms the way a careful person would
| Feature | Detail |
|---|---|
| Four apply adapters | **Greenhouse** (including the emailed security-code step), **Ashby**, **Lever** and **Workable**, driven by page structure, not screenshots. |
| 80 answer rules | Contact, address, location, work authorization, sponsorship (today and long-term), citizenship, education dates, start date, relocation, referral, prior employment and more, all filled from your presets, never hard-coded. EEO questions are always declined. |
| Salary | The midpoint of the range the posting shows; if it shows none, your market-rate preset. |
| Approved-answer bank | An answer you approve once (`profile/answers.json`) is reused on every form, with its source recorded. |
| Form inspector | `python -m engine inspect <url>` lists every question and the answer the engine would give, without filling anything. |
| Human checks respected | hCaptcha, reCAPTCHA, Cloudflare Turnstile and Ashby's bot check are detected and handed to you with the form filled and the resume ready. They are never solved or bypassed. |
| Airbags | Sensitive fields (SSN, bank, passwords), fee requests, unexpected sites, answers that drift from your presets, and per-company and daily rate caps stop the run and flag it. A `workspace/STOP` file halts everything. |
| Proof | A full-page screenshot of the confirmation page for every submission; already-submitted jobs are skipped. |
| Round-robin over tabs (v0.8) | Several applications run at once, one per tab. Each gets a time slice, then the next one runs; while one waits on the site, the others keep filling. See [Algorithms and complexity](#algorithms-and-complexity). |
| Drafted answers (v0.8) | Questions no rule covers are answered without stopping. Text questions get sentences built only from Fact Bank entries chosen for that job. "Have you done X?" is Yes only when a fact shows it, otherwise No. Every drafted answer and its fact ids go to `workspace/drafts_review.md`. Legal and EEO questions are never drafted. |
| One-command pipeline (v0.8) | `python -m engine run` scans, picks jobs, writes resumes, applies with parallel browser processes, and reports. |
| Answer from the page (v0.8) | Answer a "waiting on you" question once in the live view; it's saved with its source, reused on every form, and the job is re-queued. |

Code: `engine/apply/runner.py`, `engine/apply/scheduler.py`, `engine/apply/drafts.py`, `engine/safety.py`

### 5. Feedback: learn from what comes back
- **Inbox classifier.** Confirmation, rejection, online assessment, interview, offer, or scam, including previews that stop mid-sentence. Each outcome is linked to the applications it refers to. (`engine/feedback/inbox.py`)
- **`learn`.** Response rates by lane and ATS. (`workspace/learnings.md`)
- **`report`.** Counts only applications whose latest status is submitted *and* whose proof screenshot exists on disk.
- **Human queue.** Only what the engine can't answer from your presets or Fact Bank, with drafts that cite fact ids. (`workspace/human_queue.md`)

### 6. Memory: a knowledge graph of your search
`engine/memory/graph.py` turns the evidence into a graph that follows `engine/memory/schema.cypher`:

```
(You)-[:WRITES_AS]->(Lane)-[:SENT]->(Application)-[:AT]->(Company)
(Application)-[:INCLUDES]->(Fact)          which Fact Bank lines the resume used
(Application)-[:ANSWERED {value}]->(Question)
(Application)-[:RESULTED_IN]->(Outcome)
(Application)-[:HOSTED_ON]->(ATS)
```

A fact used by many applications is one node with many edges, so you can see which parts of your experience carry your search. `python -m engine graph` prints node and edge counts; `python -m engine graph s_rag` shows one node and everything connected to it.

### 7. MCP server: let any agent use the engine
`python -m engine mcp` runs REGEN as a [Model Context Protocol](https://modelcontextprotocol.io) server (stdio), and `.mcp.json` registers it for Claude Code.

| Tool | Returns |
|---|---|
| `engine_status` | Proof-backed counts, what's waiting on you, boards watched, outcomes |
| `applications` | Applications by status, with lane, facts used and every answer given |
| `human_queue` | What only you can do right now |
| `outcomes` | Classified replies from your inbox |
| `memory_query` | A company, Fact Bank id or lane, and everything connected to it in the graph |
| `job_queue` | Discovered jobs not yet applied to |
| `pipeline_status` | Each running applier's latest results, jobs waiting for an email code, today's verified count |
| `pipeline_run` | Starts `engine run` in the background (needs `REGEN_MCP_WRITE=1`) |
| `submit_codes` | Hands Greenhouse email codes to the jobs waiting for them (needs `REGEN_MCP_WRITE=1`) |

The two write tools only start the same CLI commands you would run, with the same airbags and log.

---

## The platform (v0.7)

```mermaid
flowchart LR
    E[Engine CLI<br/>the only writer] -->|append-only| L[(events.jsonl)]
    L -->|migrate, idempotent| P[(Postgres<br/>append-only table)]
    L --> API
    P --> API[FastAPI + Pydantic<br/>reads · one guarded write · OpenAPI]
    API -->|SSE /api/stream| WEB[Next.js + TypeScript<br/>live view · memory graph]
    API --> MCP[MCP server<br/>agents]
    W[(proof screenshots)] --> API
```

| Part | What it is | Code |
|---|---|---|
| **API** | FastAPI with typed Pydantic models (Snapshot, Application, Outcome, HumanItem, Event, Narration). Endpoints: `/api/snapshot`, `/api/applications`, `/api/human`, `/api/outcomes`, `/api/events`, `/api/narration`, `/api/graph`, `/api/proof/{file}`, and `/api/stream` (Server-Sent Events). Docs at `/docs`. | `apps/api/` |
| **Event store** | Postgres when `REGEN_DATABASE_URL` is set, otherwise the engine's own `events.jsonl`. The Postgres table keeps the log's rules: a trigger refuses updates and deletes, and lines are de-duplicated by hash, so migration is safe to re-run. | `apps/api/store.py`, `migrate.py` |
| **Live view** | One line of five stations (listening, judging, writing, applying, hearing back) and a tree of proof-backed applications, one stem per resume lane. Click any bead to open its confirmation screenshot, the Fact Bank ids its resume used, and every question with the answer given. | `apps/web/app/page.tsx` |
| **Memory graph** | Layers you open one at a time: You, then your lanes, then each lane's applications, then each application's facts, company, ATS and outcomes. Nodes bloom outward, edges carry moving light, hovering lights up a node's neighborhood, and you can pan and zoom. | `apps/web/app/graph/page.tsx` |
| **Typed client** | TypeScript types are generated from the API's OpenAPI schema (`npm run gen:api`), so the page and the API can't drift apart. | `apps/web/lib/` |
| **Stack** | `docker compose -f deploy/platform.compose.yml up -d --build` starts Postgres, the migrator, the API and the web app, all bound to 127.0.0.1, with the workspace mounted read-only. | `deploy/` |

Run it without Docker:
```bash
pip install fastapi uvicorn "psycopg[binary]"
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787     # API + docs at /docs
cd apps/web && npm install && npm run dev                          # http://127.0.0.1:3000  (graph at /graph)
```

---

## Quick start

```bash
git clone https://github.com/sameernagar-hub/regen-engine && cd regen-engine
pip install -r requirements.txt && playwright install chromium
cp -r profile.example profile           # fill in YOUR facts, presets, lanes, domains

python -m engine boards harvest         # grow the board registry from public job lists (daily)
python -m engine scan 1                 # all four ATSs, last 24 h -> workspace/queue.json
python -m engine newgrad 1              # newgrad-jobs.com leads, resolved to the employer's ATS
python -m engine alerts workspace/alerts/<date>.txt   # job-alert emails (gmail_alerts.js), resolved the same way
python -m engine batch b1 <id>,<id>     # fit gate + one tailored resume per job
python -m engine inspect <job url>      # optional: every question + the engine's answer, nothing filled
python -m engine apply batches/b1.json --dry   # fill only, screenshots in workspace/proof/
python -m engine apply batches/b1.json         # fill + submit
python -m engine run                    # or all of the above in one command (scan, pick, resumes, apply, report)
python -m engine report                 # verified submissions only
python -m pytest -q                     # tests run on profile.example/, never your data
```

Always-on discovery and the classic live view in Docker:
```bash
docker compose -f deploy/watcher.compose.yml up -d --build   # watcher + live view on http://127.0.0.1:7777
```

### Your profile (`profile/`, git-ignored)
| File | Purpose |
|---|---|
| `fact_bank.json` | The only source of resume content: facts with ids, roles, projects, skills lines, education, and overlap groups. |
| `presets.json` | Standing answers: contact, address, location, work authorization, sponsorship, citizenship, EEO (decline), education, start date, market salary. |
| `lanes.json` | Resume lanes: headline, summary and default fact order per domain. |
| `domains.json` | Discovery filters: titles, seniority, excluded employers, US-only. |
| `answers.json` | Optional: answers you approved once, reused everywhere with their source. |

---

## Architecture

```mermaid
flowchart LR
    subgraph Fuel["① Discovery"]
        ATS[Greenhouse · Ashby · Lever · Workable<br/>2,100+ live boards]
        LEADS[newgrad-jobs · job-alert emails<br/>resolved to the source]
    end
    Fuel --> F["② Fit gate<br/>eligibility · years · core stack"]
    F --> T["③ Tailor<br/>Fact Bank → lane → 1-page PDF"]
    T --> A["④ Apply<br/>4 adapters · airbags · proof"]
    A -- "personal / legal / human check" --> HQ[Human queue]
    HQ --> A
    A --> E["⑤ Feedback<br/>events · inbox outcomes"]
    E --> M["Memory graph<br/>API · web · MCP"]
    M -- "what worked, by lane and source" --> T
```

| Stage | Module |
|---|---|
| ① Discovery | `engine/discovery/` |
| ② Fit gate | `engine/tailoring/tailor.py` |
| ③ Tailor | `engine/tailoring/resume.py`, `tailor.py`, `batch.py` |
| ④ Apply | `engine/apply/runner.py`, `engine/safety.py` |
| ⑤ Feedback | `engine/feedback/` (events, inbox, learn) |
| Memory and connectors | `engine/memory/graph.py`, `engine/connectors/mcp_server.py`, `apps/api/` |

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · original design: [docs/PLAN.md](docs/PLAN.md) · frontend research: [docs/FRONTEND.md](docs/FRONTEND.md) · current state: [docs/HANDOFF.md](docs/HANDOFF.md)

---

## Algorithms and complexity

The engine runs on a laptop, so every hot path is measured and kept near-linear. Symbols: J jobs in a batch,
S jobs sleeping, T vocabulary terms (~200), F Fact Bank entries, k facts in a pool, n characters in a JD,
E events in the log, A applications.

### Round-robin scheduler (`engine/apply/scheduler.py`)
Each application is a Python generator that `yield`s at every field (a checkpoint) and `yield seconds` at every
wait. The scheduler keeps a ready queue (deque) and a sleep heap:

| Operation | Structure | Cost |
|---|---|---|
| pick the next job | `deque.popleft` | O(1) |
| quantum used up at a checkpoint → back of the queue | `deque.append` | O(1) |
| job starts waiting → sleeps until its wake time | `heapq.heappush` | O(log S) |
| wake jobs whose time has come | `heapq.heappop` | O(log S) each |
| whole batch | | O(B log J) time for B bursts, O(J) memory; only `REGEN_TABS` tabs open |

It is cooperative (a browser call can't be interrupted halfway), so the quantum is checked at checkpoints.
One job's exception is recorded and the others continue.

**Adaptive quantum.** Too small and switching overhead dominates; too large and round-robin degrades into
first-come-first-served. The textbook rule is that about 80% of CPU bursts should finish within one quantum. For
each ATS the scheduler keeps an exponentially weighted mean and variance of burst length (West's one-pass update,
α = 0.2, O(1) time and memory, no history stored) and sets

`quantum = mean + 0.84 · stddev`  (the 80th percentile of a normal), clamped to 2–20 s, default 6 s until 3 samples.

Stats persist in `workspace/sched_stats.json`, so the engine learns each ATS's rhythm across runs. Every run logs a
`schedule` event with wall time, active time, switches, per-job slices and the quanta used.

**Evidence** (`python scripts/bench_scheduler.py`, deterministic simulation of the real Ashby / Greenhouse / Lever flows):

| Batch | Sequential | Round-robin | Speed-up | Browser busy |
|---|---|---|---|---|
| 20 jobs, 3 tabs | 500 s, 144 jobs/h | 244 s, 295 jobs/h | ×2.05 | 29% → 60% |
| 40 jobs, 4 tabs | 989 s, 146 jobs/h | 395 s, 365 jobs/h | ×2.50 | 32% → 80% |

On real forms each applier process stayed about 95% busy, because every browser call blocks until the page answers.
Round-robin inside one process only reclaims the explicit waits, so `engine run` also runs several applier processes in
parallel (`--appliers N`). Every run logs its real wall time, busy time and switches as a `schedule` event.

**Company interleaving.** Before scheduling, a batch is reordered round-robin over companies (a dict of deques, O(J)),
so per-company caps and bot checks see spread-out traffic.

### Tailoring and the fit gate (`engine/tailoring/tailor.py`)

| Step | Before | Now |
|---|---|---|
| Candidate vocabulary | rebuilt from the Fact Bank on every call | built once per loaded bank, cached: O(1) |
| Term hits in a text | for each term: escape, regex cache lookup, full scan | compiled pattern per term (cached) and a `term in text` substring test first; the regex only confirms word boundaries. Same O(T·n) bound, far fewer regex scans |
| Ranking a role's facts | `list.index` inside the sort key: O(k² log k) | precomputed positions: O(k log k); each fact text matched once per JD (memo) |
| Overlap groups | O(k · groups · picked) | fact → group ids dict: O(k) |
| "Does the bank have stack X?" | per JD | once per vocabulary |

Measured on 155 real saved JDs with identical output (`python scripts/bench_tailor.py <old tailor.py>`):
`tailor()` 74.3 → 24.3 ms (×3.1), `fit()` 21.8 → 15.1 ms (×1.4).

### Event log (`engine/feedback/events.py`)
Append-only JSON lines. Writers take a cross-process lock and write each line with one `os.write` on an `O_APPEND`
descriptor, so concurrent engine processes can't tear lines. `read()` is incremental: it keeps the parsed events and
the byte offset, and parses only bytes appended since the last call (O(new lines) per call instead of O(E)); a line
still being written is left for the next call, a malformed line is skipped and counted. The rate cap and duplicate
checks run per job on top of it, and the knowledge graph uses the same reader.

### Knowledge graph (`engine/memory/graph.py`)
One pass over the log builds nodes and edges in dicts: O(E) time and memory. Linking each lane once uses a set
(the old per-application scan of every edge was O(A·E)). `neighbors()` is a single O(N + E) pass.

### Drafted answers (`engine/apply/drafts.py`)
No model and no network: O(F) to load the job's resume spec and a few regexes over the question label, so drafting
costs microseconds next to a page load. The facts it uses are the ones the tailored resume already ranked for the JD.

### Greenhouse email codes (`engine/apply/codes.py`)
Waiting jobs × codes in the inbox, both tiny. A code is only written for the job whose company the email names, and only
if the email arrived after that job started waiting.

## Principles

| Principle | How it's enforced |
|---|---|
| **No fabrication** | `resume.validate()` rejects anything outside the Fact Bank; JD-spelling aliases are checked against a fixed table. |
| **No improvised legal answers** | Work authorization, sponsorship, citizenship, arbitration and attestations come from your presets or go to you. |
| **No bypassing human checks** | CAPTCHAs, Turnstile and bot checks are detected and handed over. No accounts are created on your behalf. |
| **Discovery only on job boards** | LinkedIn, Indeed, Glassdoor, ZipRecruiter and Handshake are read for leads; applications go to the employer's own site. |
| **Local-first** | `profile/` and `workspace/` stay on your machine and out of git. Network use is limited to public job APIs and the forms you apply to. Every service binds to 127.0.0.1. |
| **Transparent** | Each resume lists its fact ids, each skip its reason, each submission its proof, each form every question and answer, and each drafted answer the facts it came from. |
| **You start it** | No background schedules (removed in v0.8). The engine runs when you run it. |
| **Lean** | Dead boards skipped, lookups cached, the event log read incrementally, the first watcher pass only seeds state. |

## Privacy and security
Your data never belongs in this repository, and CI enforces it. Every pull request and every push to `main` runs a **privacy gate**: PII patterns, forbidden paths, noreply-only commit emails, and keyed fingerprints of the maintainer's private terms. The public demo is built from anonymized events and refuses to publish if a company name would appear. See [SECURITY.md](SECURITY.md).

**Live demo: [sameernagar-hub.github.io/regen-engine](https://sameernagar-hub.github.io/regen-engine/)**, a static page that replays the last week of real activity with every company name and personal detail removed. It is rebuilt with `python -m engine site` and published from the `gh-pages` branch.

---

## Status

Every change is itemized in [CHANGELOG.md](CHANGELOG.md) with what changed, why, and how to verify it.

| Capability | State |
|---|---|
| Discovery on 4 ATSs, board registry, watcher, alert emails, lead resolution | ✅ |
| Fit gate (eligibility, clearance, sponsorship, grad window, years, core stack) | ✅ |
| Fact-Bank tailoring with JD spelling, overlap groups and audit log | ✅ |
| Apply: Greenhouse | ✅ |
| Apply: Ashby, Lever, Workable | ✅ beta (human checks go to you) |
| Airbags, kill switch, SOS email | ✅ |
| Inbox outcomes, `learn`, verified-only `report` | ✅ |
| Platform: FastAPI API, Postgres store, Next.js live view and memory graph | ✅ v0.7 first cut |
| Round-robin applying over tabs with adaptive quantum | ✅ v0.8 |
| Drafted open-ended answers from the Fact Bank, reviewable | ✅ v0.8 |
| Tests: unit, API, and headless form tests against local ATS look-alikes; coverage in CI | ✅ v0.8 |
| MCP server: read tools, plus pipeline tools behind `REGEN_MCP_WRITE=1` | ✅ v0.8 |
| Privacy gate in CI, anonymized public site | ✅ |
| Vector memory (pgvector) and facts-for-JD retrieval | 🔜 |
| Write path from the web app (answer the human queue in the page) | ✅ v0.8 (`REGEN_API_WRITE=1`, localhost only) |
| GPU "engine room" view | 🔜 v0.9 |

## Roadmap

| Release | Theme | Deliverables |
|---|---|---|
| v0.1–0.6 ✅ | Engine | Discovery, Fact-Bank tailoring, Greenhouse/Ashby apply with proof, safety, inbox loop, live view, privacy gate |
| **v0.7** ✅ first cut | Platform | FastAPI + Pydantic API, Postgres event store, Next.js live view, memory graph, MCP server, Lever and Workable adapters, job-alert emails |
| **v0.8** ✅ | Throughput, truthfully | Round-robin scheduler with adaptive time slices, parallel appliers, `engine run`, drafted answers from the Fact Bank, salary from the posted range, answer from the page, locked event log, ×3 faster tailoring, browser tests and coverage |
| v0.9 | Engine room | GPU-rendered live view: instanced board field, glowing pipeline, 3D lane tree, render-on-demand ([research](docs/FRONTEND.md)). Moved from v0.8 so v0.8 could ship throughput first |
| v0.9 | Retrieval memory | pgvector over facts and job descriptions; facts-for-JD retrieval; MCP tools for discovery and tailoring |
| v1.0 | Public release | One-command setup, docs site, stable APIs |

## Repository layout
```
regen-engine/
├── engine/            the engine (Python): discovery · tailoring · apply · feedback · memory · connectors · live
├── apps/api/          FastAPI + Pydantic API (reads, plus answers you type), Postgres migration
├── apps/web/          Next.js + TypeScript: live view (/) and memory graph (/graph)
├── deploy/            watcher, platform (db + api + web) and memory compose files
├── profile.example/   templates for your private profile/
├── tests/             pytest suite (fictional persona, never real data)
├── scripts/           privacy gate, benchmarks (bench_scheduler.py, bench_tailor.py)
├── site/              anonymized public demo (built by `python -m engine site`)
└── docs/              architecture, original plan, frontend research, handoff
```

## Contributing
Good first contributions: Workday and iCIMS adapters, more discovery sources, graph-view polish, pgvector retrieval. Read [CONTRIBUTING.md](CONTRIBUTING.md) and use the fictional fixtures (`tests/fixtures/`, `profile.example/`), never real data.

## License
[MIT](LICENSE)
