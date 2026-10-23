# REGEN: the autonomous job engine

> **Hit the role in its first hour, not its first week, with a resume that can't lie.**

REGEN is an open-source, local-first engine that runs a job search end to end:

- **Finds** roles at the source: it polls ~5,900 company boards on nine ATSs and six big-tech careers portals and resolves alerts, lists and
  careers APIs back to the employer's own posting. Your AI client can add new sources over MCP.
- **Rejects** roles you'd be screened out of before spending any effort on them.
- **Writes** one resume per job from a Fact Bank of claims you can prove.
- **Applies** on the company's own form, in parallel.
- **Proves** every submission with the confirmation page.
- **Learns** from every rejection: a feedback loop compares rejected job descriptions with the rest.
- **Shifts** speed with one control: the gearbox sets appliers and scan rate; your AI can drive every level.

It is built like infrastructure: an append-only event log, a preemptive round-robin scheduler, typed APIs, an MCP
server with 43 tools, a privacy gate in CI and 245 tests.

| Applications submitted | Boards polled | Biggest day | MCP tools | Tests |
|---|---|---|---|---|
| **282** (ledger, 10-22) | **~5,900** | **49** (2026-10-10) | **43** | **245** |

## The system in one picture

```mermaid
flowchart LR
    subgraph Discover
      ATS[9 ATSs<br/>~5,900 boards] --> Q
      AL[Alert emails · lists<br/>big-tech APIs] -->|resolve to source| Q[(queue)]
    end
    Q --> FG{Fit gate<br/>JD rules}
    FG -->|blocked| SK[skip + reason]
    FG --> TL[Tailor<br/>Fact Bank → composer → validator → PDF → ATS read-back]
    TL --> AP[Apply engine<br/>adapters · answer resolver · RR scheduler · airbags]
    AP -->|code| EC[Email codes]
    EC --> AP
    AP -->|CAPTCHA · legal · unknown| HQ[Human queue]
    AP --> EV[(events.jsonl<br/>+ proof PNGs)]
    EV --> OUT[Inbox outcomes · learn · report]
    OUT --> FB[Rejection feedback]
    FB -->|learned phrases| FG
    EV --> PL[Platform<br/>API · web · MCP]
    GB[Gearbox] -.->|appliers · scan rate| AP
    MCP[MCP: your AI client] -.->|new sources| Q
    MCP -.-> GB
```

## Map of the wiki

**Start here**

| Page | Read it for |
|---|---|
| [Ideology](Ideology.md) | The non-negotiables: truthful, transparent, local-first, lean, you-start-it |
| [How it works](How-it-works.md) | A posting's journey from discovery to a verified submission |
| [Architecture](Architecture.md) | Processes, modules, data stores, contracts between stages |
| [Metrics](Metrics.md) | Every number we publish and how to reproduce it |

**Subsystems (deep dives)**

| Page | Read it for |
|---|---|
| [Discovery](Discovery.md) | ATS adapters, board registry, watcher, alert emails, lead resolution, big-tech APIs |
| [Fit gate](Fit-Gate.md) | JD rules that block ineligible roles, and the rejection log that grows them |
| [Tailoring](Tailoring.md) | Fact Bank, lanes, the JD-first composer, validator, one-page fit, ATS read-back |
| [Apply engine](Apply-Engine.md) | Adapters per ATS, the answer resolver, dropdown matching, scheduler, airbags |
| [Email codes](Email-Codes.md) | Greenhouse security codes: matching, freshness, bounced codes, IMAP watch |
| [Outcomes and learning](Outcomes-and-Learning.md) | Event log, inbox classification, verified-only reporting, `learn` |
| [Platform](Platform.md) | FastAPI API, Next.js live view and engine room, MCP server, public site |
| [Rejection feedback](Rejection-Feedback.md) | The container that reads every rejection and teaches the fit gate (with a significance test) |
| [Gearbox](Gearbox.md) | One shift sets appliers and scan rate; the clutch couples the learned phrases |
| [MCP tools](MCP-Tools.md) | All 43 tools by engine level: discovery, fit gate, pipeline, answers, gearbox, fleet, ledger, repo |
| [Technical reference](Technical-Reference.md) | The long-form README: every feature, number, command and algorithm |

**Operating it**

| Page | Read it for |
|---|---|
| [Running the engine](Running.md) | A day's run, step by step |
| [Configuration](Configuration.md) | Profile files, presets, every `REGEN_*` environment variable |
| [Truthfulness and safety](Truthfulness-and-Safety.md) | Validator, presets-only legal answers, airbags, privacy gate |
| [Algorithms and complexity](Algorithms.md) | Scheduler, adaptive quantum, tailoring, matching: costs and measurements |
| [Testing and evidence](Testing.md) | What is tested and how |
| [Decisions](Decisions.md) | Dated design decisions and the reasons for them |
| [Roadmap](Roadmap.md) | What ships next and why |
| [FAQ](FAQ.md) | Short answers |

## Versions

| Version | Theme | Highlights |
|---|---|---|
| v0.1–0.6 | Engine | Discovery, Fact-Bank tailoring, Greenhouse/Ashby apply with proof, airbags, inbox loop, live view, privacy gate |
| v0.7 | Platform | FastAPI + Pydantic API, Postgres event store, Next.js live view, memory graph, MCP server, Lever + Workable |
| v0.8 | Throughput, truthfully | Round-robin scheduler with adaptive quantum, parallel appliers, `engine run`, drafted answers from facts |
| v0.9 / 0.9.1 | Composer, fewer stops | JD-first composer + ATS read-back, engine room, big-tech discovery, code matcher, `codes --watch`, rule fixes from live runs |
| v0.10–0.11 | Control | Control room, trust gate, first-applicant loop, priority queue, design layer |
| v0.12–0.13 | Scale-out, reach | Docker bank, atomic-claim appliers, supervisor, Postgres ledger, Workday / iCIMS / SmartRecruiters discovery |
| v0.14–0.16 | Guardrails, front door | Evals, desk, Rippling, answer queue, the radial-engine front page, proxy dataset for the public site |
| v1.0 | Public release | Security review of every local service, one version everywhere |
| **v1.1** | Feedback, gearbox, MCP everywhere | Rejection feedback container, gearbox, 43 MCP tools incl. discovery sources, `/gearbox` and `/mcp` pages |
| **v1.2** | Rules, speed | Rules view in the Fact Bank (`/api/rules`), incremental API reads + ETag 304s, one shared stream per tab |

Every page here lives in `docs/wiki/` and is reviewed in pull requests like code.
