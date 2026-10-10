# Job priority and first-applicant mode

A strong match should never wait behind fifty average ones, and the first resumes in an ATS get read first.

## Priority score (before any description is fetched)
`engine/discovery/priority.py::score(job)`, O(1) per job; the queue is sorted by it (O(Q log Q)).

| Part | Points | Signal |
|---|---|---|
| level | 4 / 2 | new grad, early career, entry, associate, "Engineer I" / II, mid |
| lane | 1–3 | title words for the user's deepest lanes (AI > backend, full stack > general) |
| fresh | 0–4 | `4 · 0.5^(hours/24)`: halves every day |
| tier | 4 / 2 | employer on the user's private tier lists (`profile/priority.json`, git-ignored) |
| sponsor | 2 | employer on the user's known-sponsor list |
| learned | 0–10 | reply rate (OA / interview / offer) of that lane, from the inbox, once a lane has 5+ submissions |

Every part is kept with the score so the order is explainable.

## JD match (after the full description is read)
`jd_match(coverage)` = share of the posting's terms the Fact Bank covers and the resume shows. The built batch is
sorted by it, so the best-matching job of the batch is filled first.

## Learning what not to open
`engine/pipeline.py::history()` reads the last 3 days of attempts (O(E)):
- an ATS where ≥ 50% of recent attempts hit a captcha / bot check is skipped and its jobs go to the assist list;
- a company whose last attempt stopped on something only the user can clear (arbitration, assessments,
  transcripts, export-control self-certification) is skipped until the user acts.
Transient failures (an email code that timed out, no confirmation page) get exactly one retry.

## First-applicant mode
`python -m engine run --loop 20` (or *Rescan every* in the control room): one full pass, then every 20 minutes a
rescan of only the last few hours of postings, applying to whatever just opened. Scans **merge** into the queue
(bounded to 21 days), so a short rescan never drops untried jobs. It runs until you stop it; it is never scheduled.

## Evidence
- `tests/test_core.py::test_priority_orders_good_jobs_first`, `test_history_learns_walls`.
