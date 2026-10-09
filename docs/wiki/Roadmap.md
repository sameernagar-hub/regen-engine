# Roadmap

Ordered by expected impact on verified applications per hour, then by reach.

| Next | Why it matters | Notes |
|---|---|---|
| Title gate: software context for "engineering lead/leader" | one off-domain role was submitted | first item in the handoff |
| Hands-free codes by default | the email code is the most frequent human touch | `codes --watch` ships; needs your app password |
| Async Playwright inside each applier | each applier is ~95% busy on sync waits; async overlaps browser round trips in one process | today's scale-out is processes |
| Workday and iCIMS adapters | most unresolved leads live there | you create the account, the engine fills |
| Big-tech coverage: Apple, Netflix, Google, Meta | the user wants top-tier employers | public search endpoints to be found; submit stays yours |
| Remaining form gaps | each one is a `NEEDS YOU` | "how did you hear" selects without a careers option, SMS blocks, "ever employed by" selects |
| Retrieval memory (pgvector) | pick facts by meaning, not only by term overlap | facts and JDs as vectors; MCP tools |
| Bandit over strategy | learn which lane, source and timing earn replies | reward = reply or passing the screen |
| Engine room GPU view | readable at a glance, still uncluttered | instanced board field, glowing pipeline, 3D lane tree |
| v1.0 | anyone can run it | one-command setup, docs site, stable APIs |

Related: [Decisions](Decisions.md) · [Architecture](Architecture.md) · [Metrics](Metrics.md)
