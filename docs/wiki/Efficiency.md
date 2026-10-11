# Efficiency proof

Each claim below has the measurement or test that backs it.

| Claim | Proof |
|---|---|
| Picking k of Q jobs costs O(Q + k log Q), not O(Q log Q) | `engine/pipeline.py:select` (lazy `heapq`); B1: 5.5 ms vs 31.6 ms for Q=50k, identical picks |
| Applying scales with containers, not one machine's browser | `--scale applier=N`; 5 appliers × 4 tabs ran from the bank on 2026-10-10 (pipeline log: `dispatch: ... -> batches/inbox (container worker)` × 5) |
| No job is applied twice across workers | B3: 200/200 exactly-once over 3 runs; `test_worker_claims_each_batch_once` |
| Tabs overlap waiting (page loads, uploads) | round-robin scheduler, S1: ×2.05 vs sequential |
| Email codes need no human | relay log: `code -> torcrobotics_...` within one 20 s tick; the first tick on the bank delivered 3 codes |
| The queue holds only fillable work | `prune()`: on 2026-10-10 only 17 of 229 queued jobs were fillable; after the 30-day scan, 488 usable kept and 179 dropped |
| Freshest jobs first | strict bands (hour, day, week, cold), `test_select_prefers_fresh_band` |
| Disk stays bounded | `engine clean` every pass; first run freed 459 MB; pending resumes protected |
| Zero model cost | no API key anywhere in `requirements.txt` or `.env.example`; AI only through your own MCP client |
