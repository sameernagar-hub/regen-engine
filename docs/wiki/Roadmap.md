# Roadmap

Ordered by expected impact on verified applications per hour, then by reach.

| Next | Why it matters | Notes |
|---|---|---|
| Missing answers from benchmark B2 | 67.5% of non-legal questions answerable; each gap is a `NEEDS YOU` | `scripts/bench_system.py` lists them |
| Supervisor view of the containers | see each worker's health and batch in /control | v0.12 runs pipeline + N appliers + relay |
| Benchmarks B5 to B7 | submissions/hour by N, code latency, fit-gate precision | [Benchmarks](Benchmarks) |
| Async Playwright inside each applier | each applier is ~95% busy on sync waits; async overlaps browser round trips in one process | scale-out today is containers (v0.12) |
| Workday and iCIMS form fillers | discovery + reach list shipped in v0.13; the form sits behind your account | you create the account, the engine fills |
| Big-tech coverage: Apple, Netflix, Google, Meta | the user wants top-tier employers | public search endpoints to be found; submit stays yours |
| Retrieval memory (pgvector) | pick facts by meaning, not only by term overlap | facts and JDs as vectors; MCP tools |
| Bandit over strategy | learn which lane, source and timing earn replies | reward = reply or passing the screen |
| Engine room GPU view | readable at a glance, still uncluttered | instanced board field, glowing pipeline, 3D lane tree |
| v1.0 | anyone can run it | one-command setup, docs site, stable APIs |

Related: [Decisions](Decisions.md) · [Architecture](Architecture.md) · [Metrics](Metrics.md)

## Done recently
- v0.12: Docker execution room and data bank, atomic-claim workers, freshness bands, onsite priority, code relay
  (hands-free codes without an app password), queue prune, disk hygiene, system benchmarks.
- v0.10 / v0.11: title gate for non-software disciplines, control room, trust gate, first-applicant loop, priority.
