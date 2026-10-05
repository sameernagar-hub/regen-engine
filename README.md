# REGEN · the job-hunting engine

> **The fuel for job hunting.** An open-source engine that finds jobs at the source, minutes after they go live, writes a truthful resume for each one, applies automatically within your domain, and learns from every outcome through an agentic memory that runs in Docker.

*REGEN is a working name. Branding comes later. The engine is what matters.*

[![status](https://img.shields.io/badge/status-v0.4%20alpha-orange)](#roadmap) [![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE) [![python](https://img.shields.io/badge/python-3.10%2B-informational)](pyproject.toml)

---

## What this is (and isn't)

**This isn't another auto-apply SaaS.** Tools like Jobright, LazyApply or Simplify Copilot are finished products: you use their UI, their filters and their pipeline, and your data lives on their servers.

**This is an engine.** It's the part underneath those products, open source and local-first, built to be embedded:

| Use it as… | How |
|---|---|
| **A project by itself** | Clone it, add your profile, and run `python -m engine scan → batch → apply`. |
| **A library** | `from engine.discovery.greenhouse import scan` and build your own app on top. |
| **A connector / plugin** *(v0.5)* | An MCP server, so Claude (Desktop or Code) or any agent can drive it in plain English, plus a REST API and webhooks for dashboards and other products. |

## Why it works

Most job seekers lose before they apply. A role is live on the company's own careers page for hours or days before it reaches LinkedIn, and by then hundreds of people are ahead. Auto-apply bots respond with volume: one generic resume sent 1,000 times through Easy Apply, until the account gets banned.

The engine makes the opposite bet:

| Principle | In practice |
|---|---|
| **Be early** | Poll about 2,300 company ATS boards (Greenhouse, Ashby, Lever, Workable) plus GitHub job lists and newgrad-jobs.com, and `watch` for postings that are minutes old. Apply at the source, not the mirror. |
| **Be specific** | Every job gets its own one-page resume, built from your **Fact Bank** and routed to the right **domain lane** (backend, platform, full-stack, AI…). |
| **Be honest** | The code can't invent a skill, number, employer or date. Tailoring only *selects and orders* Fact Bank entries, and every resume logs the fact ids it used. Legal answers come only from your presets; arbitration needs your per-company OK. |
| **Stay local** | Profile, history, resumes and browser session live on your machine. The only network calls are to public job APIs and the forms you apply to. No third-party service sees your data, and calls are kept to a minimum (dead boards skipped, lookups cached). |
| **Get smarter** | Every action and outcome becomes an event. The agentic memory turns events into a knowledge graph and refines what the engine does next. |

---

## Architecture

```mermaid
flowchart LR
    subgraph Fuel["① Discovery: the fuel"]
        GH[Greenhouse boards API]
        GL[GitHub job lists]
        AL[Ashby · Lever<br/><i>next</i>]
        BB[LinkedIn · Indeed<br/><i>discovery only</i>]
    end
    subgraph Memory["Agentic memory · Docker"]
        KG[(Knowledge graph<br/>Neo4j)]
        VS[(Vectors + events<br/>pgvector)]
    end
    Fuel --> F["② Filter & score<br/>domain · level · visa · dedupe"]
    F --> T["③ Tailor<br/>Fact Bank → lane → 1-page PDF"]
    T --> A["④ Apply<br/>ATS adapters · Playwright"]
    A -- "unknown / CAPTCHA / legal" --> HQ[Human queue]
    HQ --> A
    A --> E["⑤ Feedback<br/>events · proof · email"]
    E --> Memory
    Memory -- "facts · approved answers · winning variants" --> T
    Memory -- "learned filters · fit priors" --> F
    Memory -- "site memory" --> A
```

| Stage | Module | What it does |
|---|---|---|
| ① **Discovery** | `engine/discovery/` | Scans your list of Greenhouse boards in parallel (about 350 in seconds) plus the SimplifyJobs feed. Normalizes everything into one queue and tags each job's ATS. |
| ② **Filter** | `profile/domains.json` | Your domain as rules: titles, level, locations and sponsorship stance. Dedupes against every past application. |
| ③ **Tailor** | `engine/tailoring/` | Fetches the job description, routes it to a lane, builds a Fact-Bank-only resume, auto-fits it to one page, and flags questions that need you. |
| ④ **Apply** | `engine/apply/` | Fills ATS forms by DOM structure (no screenshot-and-click loops, about 10 s per form), submits only when every required answer is known, pauses for the Greenhouse email security code, and saves a full-page proof. |
| ⑤ **Feedback** | `engine/feedback/` | An append-only event log of every discovery, resume, application and outcome. This is the raw signal for learning. |
| **Memory** | `engine/memory/` + `deploy/` | Semantic memory (profile graph), episodic memory (jobs, applications, outcomes) and procedural memory (how each ATS works) in a local Neo4j + pgvector stack. |

The full design is in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**. The original deep-dive design (sources, scoring funnel, outreach, costs) is in **[docs/PLAN.md](docs/PLAN.md)**.

### The feedback loop

```mermaid
sequenceDiagram
    participant E as Engine
    participant M as Memory
    participant U as You
    E->>M: applied(job, lane, facts, answers)
    E->>M: outcome(job, interview | rejection | silence)
    M->>M: lane × domain × source × timing → reply rate
    M-->>E: prefer winning lane · drop dead sources · propose new filters
    E->>U: human queue, only what memory can't answer
    U->>M: your answer is saved and reused next time
```

The loop does three things. The human queue shrinks over time, because approved answers are reused. Resume lanes compete, and the one that gets replies wins. And the graph proposes new filters, such as "every job with a 2027 grad window has been a misfit, so exclude it."

---

## Scope

**In scope:**
- Automatic applications **within your domain**: discovery → filter → tailor → apply → verify.
- A **knowledge graph of your profile** (facts, skills, projects, preferences) in an agentic memory that runs in Docker.
- A **feedback loop** that refines filters, resume lanes and answers from real outcomes (confirmations, OAs, interviews, rejections).
- Being an **embeddable engine**: CLI, Python library, MCP server, REST API and webhooks, plugin packaging.
- Local-first by default. Your profile and history never leave your machine unless you connect a hosted store.

**Out of scope (by design):**
- Fabricating experience, or generating legal or attestation answers.
- Solving CAPTCHAs, or creating accounts on your behalf.
- Bot-applying on LinkedIn, Indeed or Handshake. Their terms forbid it, so they're used only for discovery and routing to the company's ATS.

---

## Status: v0.3 alpha

The first real run applied to **7 jobs** (Greenhouse + Ashby), each with its own tailored resume. v0.4 widened discovery from 345 to about 2,300 boards and hardened the filler. Every change is in **[CHANGELOG.md](CHANGELOG.md)**; live state and next fixes are in **[docs/HANDOFF.md](docs/HANDOFF.md)**.

| Capability | State |
|---|---|
| Greenhouse · Ashby · Lever · Workable discovery (~2,300 boards, ~45 s) | ✅ v0.4 |
| `watch`: new-posting alerts + webhook | ✅ v0.4 |
| newgrad-jobs.com leads resolved to the employer's ATS | ✅ v0.4 |
| JD fit gate (citizenship, clearance, sponsorship, years, grad window) | ✅ v0.4 |
| Per-job Fact-Bank tailoring + coverage + fact-id audit log | ✅ v0.4 |
| `inspect`: preview any form's fields and answers | ✅ v0.4 |
| Greenhouse apply | ✅ working |
| SimplifyJobs feed · event log · `status` | ✅ working |
| Ashby apply | ⚠️ beta |
| Lever / Workable apply | 🔜 resume prepared, you click apply |
| Memory stack (Docker) | 🧱 stack defined, ingesters next |
| Gmail outcome loop | 🔜 |
| MCP / REST connectors | 🔜 |

---

## Quick start

```bash
git clone https://github.com/sameernagar-hub/regen-engine && cd regen-engine
pip install -r requirements.txt && playwright install chromium
cp -r profile.example profile           # fill in YOUR facts, presets, lanes, domains

python -m engine boards harvest         # grow the board registry from public GitHub job lists (daily is plenty)
python -m engine scan 1                 # Greenhouse + Ashby + Lever + Workable, last 24 h -> workspace/queue.json
python -m engine newgrad 1              # newgrad-jobs.com leads, resolved to the employer's own ATS
python -m engine watch 10               # or: poll every 10 min and print only brand-new matches
python -m engine feed 7                 # SimplifyJobs new-grad feed -> workspace/feed_queue.json
python -m engine batch b1 <id>,<id>     # fit gate + tailored resumes -> workspace/batches/b1.json
python -m engine inspect <job url>      # optional: every question on the form + the engine's answer
python -m engine apply batches/b1.json --dry   # fill only; check workspace/proof/
python -m engine apply batches/b1.json         # fill + submit (already-submitted jobs are skipped)
python -m engine status                 # outcomes from the event log
python -m pytest -q                     # tests (run on profile.example/, never your data)
```

Optional memory stack:

```bash
cp .env.example .env                    # set passwords
docker compose -f deploy/docker-compose.yml --env-file .env up -d
```

### Your profile (`profile/`, git-ignored)

| File | Purpose |
|---|---|
| `fact_bank.json` | The only source of resume content. Every bullet has an id and must be true. |
| `presets.json` | Standing answers: contact, location, work authorization, sponsorship, EEO, education. |
| `lanes.json` | Your domains as resume lanes (headline, summary, ordered fact ids) plus routing rules. |
| `domains.json` | Discovery filters: titles, level, excluded employers, US-only (defaults in `engine/discovery/filters.py`). |
| `answers.json` | *Optional.* Answers you approved once (`pattern`, `answer`, `source`), reused on every form. |

---

## Repository layout

```
regen-engine/
├── engine/                     the engine (Python package)
│   ├── __main__.py             CLI: scan · newgrad · watch · boards · feed · batch · tailor · inspect · apply · status
│   ├── config.py               profile/ and workspace/ paths
│   ├── discovery/              ① fuel: ats.py (4 ATS APIs + registry), scan, watch, newgrad, filters
│   ├── tailoring/              ③ Fact-Bank resume builder, per-job tailor + fit gate, batch builder
│   ├── apply/                  ④ Playwright ATS adapters, form inspector, human queue
│   ├── feedback/               ⑤ append-only event log
│   ├── memory/                 agentic memory: graph schema, design (v0.4)
│   └── connectors/             MCP / REST / plugin (v0.5)
├── deploy/docker-compose.yml   memory stack: Neo4j + Postgres/pgvector
├── profile.example/            templates for your private profile/
├── tests/                      pytest suite (runs on profile.example/)
├── CHANGELOG.md                every change: what, why, how to verify
├── workspace/                  runtime state (git-ignored): queue, resumes, proof, events
└── docs/
    ├── ARCHITECTURE.md         system design
    ├── PLAN.md                 original deep-dive design
    └── HANDOFF.md              current state, known bugs, how to resume
```

---

## Roadmap

| Release | Theme | Deliverables |
|---|---|---|
| **v0.1–0.3** ✅ | **Engine core** | Greenhouse + GitHub-feed discovery · Fact-Bank tailoring with validator · Greenhouse/Ashby apply with proof and human queue · email-code pause · event log · CLI + package |
| **v0.4** ✅ | **Sources & reliability** | Greenhouse/Ashby/Lever/Workable discovery · board registry + harvest · `watch` + webhook · newgrad-jobs leads · JD fit gate · per-job Fact-Bank tailoring + audit log · `inspect` · answer bank · runner timeouts + double-apply guard · tests |
| **v0.4.x** | **Agentic memory** | Ingest the profile and events into Neo4j + pgvector · facts-for-JD retrieval · approved-answer memory · procedural site memory |
| **v0.5** | **Connectors** | MCP server (`discover_jobs`, `tailor_resume`, `apply`, `queue_status`, `memory_query`, `engine_control`) · REST + webhooks · Claude Code plugin |
| **v0.6** | **Feedback loop** | Gmail reader (security codes + outcome classification) · lane and timing bandits · learned filters proposed by the graph |
| **v0.7** | **Coverage** | Ashby hardening · Lever + Workable apply adapters · YC Work at a Startup (in your browser session) · Workday and iCIMS (you create the account, the engine fills) |
| **v0.8** | **Always on** | Scheduler (every 15 min) · LLM fit scoring · dashboard (pipeline, human queue, response rates) |
| **v1.0** | **First public release** | Stable APIs · one-command setup · docs site · branding |

Beyond v1: recruiter and hiring-manager outreach, interview-prep packets from the job's graph neighborhood, and multi-profile support.

---

## Guardrails

1. **No fabrication**: `resume.validate()` rejects anything not in the Fact Bank.
2. **No improvised legal answers**: they come from presets only. Unknown answers go to the human queue.
3. **No CAPTCHA bypassing and no bot-created accounts.**
4. **Discovery-only on LinkedIn, Indeed and Handshake.**
5. **Your data stays yours**: `profile/` and `workspace/` are git-ignored and local. Nothing goes to third-party services; network use is limited to public job APIs and the forms you apply to.
6. **Transparent**: every resume event lists the fact ids it used, every skipped job logs the JD reason, and every submission saves a full-page proof.
7. **Lean**: as few external calls as possible. Dead boards are skipped, resolutions are cached, and the first `watch` poll only seeds state.

## Contributing

Issues and PRs are welcome, especially ATS adapters (Lever, Workday, iCIMS), discovery sources, and memory ingesters. Never commit real profile data. Use `profile.example/` for fixtures.

## License

[MIT](LICENSE)
