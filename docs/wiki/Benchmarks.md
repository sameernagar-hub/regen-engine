# Benchmarks

`python scripts/bench_system.py` runs every benchmark and prints one JSON line per benchmark. Each one compares a component
against a baseline or a real corpus, so a gap shows up as a number. **Rule: when a new failure mode is found,
add a benchmark for it.** The list only grows.

| # | Benchmark | What it measures | Baseline | Result (2026-10-10) |
|---|---|---|---|---|
| B1 | `select` | top-k pick with freshness bands: lazy heap vs full sort, 50k synthetic jobs, k=100 (same picks asserted) | `sorted()` 31.6 ms | heap **5.5 ms**, ×5.8 |
| B2 | `answers` | share of every question the engine ever stopped on (297, from `events.jsonl`) that rules + saved answers answer **now** | 0 | **67.5%** of non-legal (158 of 234); 63 are legal/EEO and stay yours |
| B3 | `claims` | 8 threads race for 200 inbox batches; each must be claimed exactly once | — | rename-only claim: **233 claims for 200 (bug)**; lock-file claim: **200/200, 3 of 3 runs** |
| B4 | `coverage` | your JD terms that reach the resume, last 200 resumes | 88% median before the coverage fill | median **100%**, 64.5% of resumes at full coverage, ATS read-back median **100** |
| S1 | `scripts/bench_scheduler.py` | round-robin tabs vs sequential, seeded | sequential | ×2.05 throughput |
| S2 | `scripts/bench_tailor.py` | tailoring time per resume | v0.7 | ×3 faster (v0.8) |

## What the benchmarks found
- **B3** caught a real race: on Windows, `os.rename` let two workers claim the same batch. The claim is now an exclusive
  lock file (`O_CREAT|O_EXCL`), atomic on every filesystem.
- **B2** lists the unanswered questions (`missing_sample`). Each is a missing rule or preset: for example, "currently
  based in <city>" (needs the city-match rule) and "transitioning service member" (needs a preset).

## Next benchmarks to add
- B5: end-to-end submissions per hour per worker count (1, 3, 5), from `pipeline` report events.
- B6: code latency, from email `issued` time to `codes/*.txt` written (relay log).
- B7: fit-gate precision, the share of rejections whose JD had a blocker the gate missed (from `outcome` events).
