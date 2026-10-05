# Handoff: where the engine stands (v0.4, 2026-10-05)

Full list of changes, with how to verify each: **[CHANGELOG.md](../CHANGELOG.md)**.

## Daily loop (about 10 minutes of your attention)
```bash
python -m engine boards harvest      # once a day: grow the board registry
python -m engine scan 1              # ~2,300 boards (Greenhouse/Ashby/Lever/Workable), last 24 h
python -m engine newgrad 1           # newgrad-jobs.com leads -> employer ATS (rest in workspace/leads.json)
python -m engine batch b8 <id,...>   # fit gate skips ineligible jobs; tailored, Fact-Bank-only resumes
python -m engine apply batches/b8.json    # submits when every required answer is known
python -m engine status
```
Or leave `python -m engine watch 10` running and batch whatever it announces.

**Greenhouse email codes:** at the code step the runner writes `workspace/WAITING_FOR_CODE` (the form URL) and waits for `workspace/code.txt`. The operator (an agent with Gmail open in Chrome, or you) searches `security code newer_than:10m` and writes the 8-character code.

**Human queue:** `workspace/human_queue.md` lists only questions the engine can't answer from presets or the Fact Bank, with drafts that cite fact ids. Answers you approve can go into `profile/answers.json` and are reused on every form.

## What works
- Discovery: 4 ATS APIs, board registry with harvest and dead-board skipping, `watch` with webhook, newgrad-jobs resolution, SimplifyJobs feed.
- Fit gate: citizenship/ITAR, clearance, no-sponsorship, grad window, years above level. Skips are logged as `SKIPPED` events and never re-queued.
- Tailoring: per-job selection and ordering of Fact Bank entries. The `resume` event lists fact ids and JD-term coverage.
- Apply: Greenhouse reliable; Ashby works for most boards. Each field is logged, actions time out, already-submitted jobs are skipped.
- `inspect <url>` shows every field and the engine's answer before applying.

## Known gaps / next fixes (priority order)
1. **Lever + Workable apply adapters.** Discovery and resumes exist; these jobs currently go to the human queue.
2. **YC Work at a Startup.** Discovery works in-browser (your session; the key never leaves the page). Applying sends a founder message, so it needs your approval per batch (drafts in `workspace/outreach/`).
3. **newgrad-jobs resolution rate (~10%).** Most unresolved leads are Workday/iCIMS/custom portals. Next: add SmartRecruiters/Recruitee fetchers and a company→ATS hint table.
4. **Gmail code step** is still operator-driven. A local IMAP reader with your app password, kept in `.env`, would close it without any third-party API.
5. **Memory ingesters** (`fact_bank.json` + `events.jsonl` → Neo4j/pgvector).
6. **Watcher memory:** stream each board through the filter instead of holding ~110k postings (now ~750 MB in Docker).
7. **Scheduler:** run `watch` as a service and auto-build batches for jobs that pass the fit gate.
