# Benchmarks

`python -m engine bench [--save]` (or `python scripts/bench_system.py`) runs every benchmark and prints one JSON line per benchmark. Each one compares a component
against a baseline or a real corpus, so a gap shows up as a number. **Rule: when a new failure mode is found,
add a benchmark for it.** The list only grows.

| # | Benchmark | What it measures | Baseline | Result (2026-10-10) |
|---|---|---|---|---|
| B1 | `select` | top-k pick with freshness bands: lazy heap vs full sort, 50k synthetic jobs, k=100 (same picks asserted) | `sorted()` 31.6 ms | heap **5.5 ms**, ×5.8 |
| B2 | `answers` | share of every question the engine ever stopped on (297, from `events.jsonl`) that rules + saved answers answer **now** | 0 | **67.5%** of non-legal (158 of 234); 63 are legal/EEO and stay yours |
| B3 | `claims` | 8 threads race for 200 inbox batches; each must be claimed exactly once | — | rename-only claim: **233 claims for 200 (bug)**; lock-file claim: **200/200, 3 of 3 runs** |
| B4 | `coverage` | your JD terms that reach the resume, last 200 resumes | 88% median before the coverage fill | median **100%**, 64.5% of resumes at full coverage, ATS read-back median **100** |
| B2 (10-11) | `answers` | same, after the B2 rules (city match, service member, contractor, eligible for employment) and the option fallback | 67.5% | **71.0%** (169 of 238 non-legal) |
| B5 | `rate` | verified submissions per active hour, per day (last 7 days) | 10-05: 6.7/h | 10-10: **16.3/h** (5 Docker appliers + live codes); 10-11: 0.75/h while the Gmail tab was frozen |
| B6 | `codes` | seconds a form waits for its email code (`code` events) and how many forms timed out on a code | — | instrumented 10-11; timeouts counted from the ledger |
| B7 | `fit gate` | today's `fit()` re-run on the stored JD of every submitted job: rejections it would now block vs non-rejected it would block | — | 81 submitted with a stored JD, 2 rejections: **0%** caught (generic rejects, no JD blocker), 3.8% of the rest would now be blocked by newer rules |
| S1 | `scripts/bench_scheduler.py` | round-robin tabs vs sequential, seeded | sequential | ×2.05 throughput |
| S2 | `scripts/bench_tailor.py` | tailoring time per resume | v0.7 | ×3 faster (v0.8) |

## What the benchmarks found
- **B3** caught a real race: on Windows, `os.rename` let two workers claim the same batch. The claim is now an exclusive
  lock file (`O_CREAT|O_EXCL`), atomic on every filesystem.
- **B2** lists the unanswered questions (`missing_sample`). Each is a missing rule or preset: for example, "currently
  based in <city>" (needs the city-match rule) and "transitioning service member" (needs a preset).

- **B5** shows codes are the throughput limit: the same 5 appliers did 16.3/h with codes delivered within a minute and
  0.75/h when the Gmail tab froze. The fleet view (`/control`, `python -m engine fleet`) now flags a silent tab.
- **B7**: the two rejections with a stored JD had no blocker in the text, so they are not gate misses; the 3.8% are
  submissions the newer rules (citizenship in form labels, defense, grad window) would now skip.

## Next benchmarks to add
- B5 by worker count (1, 3, 5) under the same queue, once fleet heartbeats have a few days of history.
- B8: form completion, the share of opened forms that reach submit, per ATS.
