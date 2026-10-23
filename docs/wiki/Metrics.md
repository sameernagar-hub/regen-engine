# Metrics

Every published number, where it comes from and how to reproduce it. Numbers that can't be reproduced aren't
published.

| Metric | Value | Reproduce |
|---|---|---|
| Applications submitted | 282 to date (2026-10-22) | ledger: latest status `SUBMITTED` per posting; `python -m engine report` lists those whose proof is still on disk (proofs are pruned after 90 days) |
| Best day | 49 (2026-10-10) | `python -m engine report 2026-10-10` |
| Boards polled | ~5,950 live (6,362 listed, 406 of them dead); 'hot' passes rescan ~3,460 every 5 min in gear 2 | `workspace/boards.json`; a full scan prints the count |
| Fresh postings per hot scan | ~14,300 of ~157,000 postings (fresh window), ~1,000 after the title gate | `python -m engine scan 1` output |
| ATS read-back | 77–100% of matched JD terms | `resume` events → `coverage.ats.score` |
| Scheduler throughput | ×2.05 (3 tabs), ×2.5 (4 tabs) vs sequential | `python scripts/bench_scheduler.py 20 3` (seeded) |
| Tailoring speed | ×3 vs v0.7 | `python scripts/bench_tailor.py` |
| Tests | 245 passing | `python -m pytest -q` |
| Outcomes read from mail | 271 confirmations, 80 rejections, 4 assessments, 1 scam flagged (10-22) | `outcome` events; `workspace/feedback.md` |
| Learned fit-gate rules | 0 active, 14 proposed (10-22): 952 phrases tested on 170 JDs, none significant after Bonferroni | `python -m engine feedback --no-imap` |
| MCP tools | 43 (13 write) | `/api/control/mcp`, [MCP tools](MCP-Tools) |
| Lead resolution | alerts 45 relevant → 6 at source; newgrad 215 → 34 | `engine alerts`, `engine newgrad` output |
| Big-tech roles ready | 6 portals; 66 new roles on the first 6-portal run (10-21) | `python -m engine bigtech 3` |

## What a "verified application" means

The company's confirmation page was reached and saved as a full-page screenshot, *and* the event log's latest status
for that URL is `SUBMITTED`. Form-filled-but-unsubmitted, CAPTCHA-blocked or unconfirmed attempts are not counted.

## Funnel on a strong day (2026-10-09)

Unique jobs touched: 113 → skipped by the fit gate 39 → needs you (legal, CAPTCHA, self-certification) 24 → failed
or errored on site 21 → flagged by airbags 1 → **submitted 28**.

Related: [Testing and evidence](Testing.md) · [Outcomes and learning](Outcomes-and-Learning.md)
