# Decisions

Dated design decisions, newest first. Each says what was decided and why.

## 2026-10-07 (v0.8)
- **Round-robin instead of one job at a time.** Applications are mostly waiting on the site; time-sharing tabs roughly
  doubles throughput (×2.05 at 3 tabs in the benchmark) without making any single form faster or riskier.
- **Generators, not threads.** Playwright's sync API is single-threaded and a persistent browser profile can't be shared
  between processes. Generators give explicit, testable switch points and need no locks inside the applier.
- **Quantum from the 80th percentile of bursts, per ATS.** Standard RR guidance; EWMA keeps it O(1) and adapts as sites change.
- **Draft open-ended answers instead of parking the job** (requested by the candidate). Drafts are Fact Bank sentences
  only, logged with fact ids, and never touch legal, EEO or salary questions. Parking cost more applications than any
  draft could cost in quality.
- **No background schedules** (requested by the candidate). Scheduled runs failed silently when the environment changed
  and ran at times nobody was watching. The engine now runs when started.
- **Lock the event log.** Two processes tore lines on Windows; correctness of the evidence comes first.
- **Engine room (GPU view) moved to v0.9** so v0.8 could ship throughput and correctness first.

## 2026-10-06 (v0.6–0.7)
- **Fit gate from rejection analysis.** Fast rejections (34–45 h) pointed at automated knockouts on years and core stack,
  so those became blockers before any resume is written.
- **Job-alert emails as a lead source.** The alerts list real roles; resolving them to the employer's ATS keeps
  applications on the employer's own site.
- **Public demo from anonymized events only**, behind a leak check.

## 2026-10-04/05 (v0.1–0.5)
- **ATS-first discovery.** Company boards publish postings hours before the big job boards syndicate them.
- **Fact Bank + validator** as the only source of resume content.
- **LinkedIn, Indeed, Handshake: discovery only.** Applications go to the employer.
- **CAPTCHAs and bot checks go to a human.** Never solved or bypassed.
