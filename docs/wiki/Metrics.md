# Metrics

Every published number, where it comes from and how to reproduce it. Numbers that can't be reproduced aren't
published.

| Metric | Value | Reproduce |
|---|---|---|
| Verified applications | 69 to date (2026-10-09) | `python -m engine report`: counts `SUBMITTED` + proof screenshot on disk |
| Best day | 28 (2026-10-09) | `python -m engine report 2026-10-09` |
| Boards polled | ~2,370 | `workspace/boards.json`; a full scan prints the count |
| Fresh postings per full scan | ~3,400 before filtering | `python -m engine scan 1` output |
| ATS read-back | 77–100% of matched JD terms | `resume` events → `coverage.ats.score` |
| Scheduler throughput | ×2.05 (3 tabs), ×2.5 (4 tabs) vs sequential | `python scripts/bench_scheduler.py 20 3` (seeded) |
| Tailoring speed | ×3 vs v0.7 | `python scripts/bench_tailor.py` |
| Tests | 95 passing | `python -m pytest -q` |
| Lead resolution | alerts 45 relevant → 6 at source; newgrad 215 → 34 | `engine alerts`, `engine newgrad` output |
| Big-tech roles ready | 43 on first run | `python -m engine bigtech 3` |

## What a "verified application" means

The company's confirmation page was reached and saved as a full-page screenshot, *and* the event log's latest status
for that URL is `SUBMITTED`. Form-filled-but-unsubmitted, CAPTCHA-blocked or unconfirmed attempts are not counted.

## Funnel on a strong day (2026-10-09)

Unique jobs touched: 113 → skipped by the fit gate 39 → needs you (legal, CAPTCHA, self-certification) 24 → failed
or errored on site 21 → flagged by airbags 1 → **submitted 28**.

Related: [Testing and evidence](Testing.md) · [Outcomes and learning](Outcomes-and-Learning.md)
