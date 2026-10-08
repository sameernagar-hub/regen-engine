# REGEN wiki

REGEN is an open-source job engine. It finds roles minutes after they're posted on the company's own applicant
tracking system (ATS), writes one resume per job from facts you can prove, applies on the company's own site, and
keeps the evidence (a confirmation screenshot, every question and answer, the facts each resume used).

This wiki is for people who want to understand **why** it is built the way it is, not only how to run it.
The code-level reference lives in the repository: [README](../../README.md), [ARCHITECTURE](../ARCHITECTURE.md),
[CHANGELOG](../../CHANGELOG.md).

## Pages
| Page | What it covers |
|---|---|
| [Ideology](Ideology.md) | The principles: truthful, transparent, local-first, lean, you-start-it |
| [How it works](How-it-works.md) | The pipeline from a job posting to a verified submission |
| [Algorithms and complexity](Algorithms.md) | The scheduler, the adaptive quantum, tailoring, the event log, with measurements |
| [Truthfulness and safety](Truthfulness-and-Safety.md) | How the engine avoids inventing anything, and the airbags that stop it |
| [Running the engine](Running.md) | A day's run, step by step, including email codes and the inbox |
| [Decisions](Decisions.md) | Dated design decisions and why they were made |
| [Testing and evidence](Testing.md) | What is tested, how, and how to reproduce every number in the docs |
| [FAQ](FAQ.md) | Short answers to common questions |

## Versions at a glance
| Version | Theme |
|---|---|
| v0.1–0.6 | Engine: discovery, Fact-Bank tailoring, Greenhouse/Ashby apply with proof, airbags, inbox loop, live view, privacy gate |
| v0.7 | Platform: FastAPI API, Postgres event store, Next.js live view, memory graph, MCP server, Lever and Workable |
| **v0.8** | Throughput, truthfully: round-robin scheduler, drafted answers from the Fact Bank, answer from the page, locked event log, faster tailoring, form tests |
| v0.9 | Engine room (GPU view), retrieval memory |

This wiki is generated from `docs/wiki/` in the repository, so every page is reviewed in a pull request like code.
