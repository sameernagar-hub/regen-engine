# Handoff: where the engine stands (v0.8, 2026-10-07)

Every change, with how to verify it: **[CHANGELOG.md](../CHANGELOG.md)**. Ideas and design notes: **[the wiki](wiki/Home.md)**.

## ▶ Resume here (last stop: 2026-10-07, night)
**State:** branch `v0.8` (PR open, CI must be green). v0.8 = round-robin scheduler, drafted answers from the Fact Bank,
answer from the page, locked + incremental event log, ×3 faster tailoring, form tests + coverage, wiki.
**No schedules.** The Windows task "REGEN public feed" and the daily Claude routine are disabled (user decision): the
engine runs only when you start it. Re-enable nothing without asking.

**Run a day (about 10 minutes of attention):**
```bash
python -m engine scan 1                     # ~2,300 boards, last 24 h  -> workspace/queue.json
python -m engine newgrad 1                  # new-grad leads -> employer ATS
python -m engine batch b1 <id,id,...>       # fit gate + tailored Fact-Bank resumes -> batches/b1.json
REGEN_TABS=3 python -m engine apply batches/b1.json      # round-robin over 3 tabs
```
A second applier can run next to the first with its own browser profile:
`REGEN_PW_PROFILE=pw-profile-2 python -m engine apply batches/b2.json` (the event log is locked, so this is safe).

**Greenhouse email codes:** a waiting job writes `workspace/codes/<board>_<id>.wait`. Run
`engine/discovery/gmail_codes.js` in a signed-in Gmail tab and pass its output to `python -m engine codes '<json>'`;
a code only goes to the job whose company the email names. (`code.txt` still works when one job is waiting.)

**Inbox:** read job replies (Gmail search `newer_than:2d (application OR interview OR assessment OR unfortunately)`),
save them as `[{id,date,from,subject,snippet}]` and run `python -m engine inbox <file>`, then `python -m engine learn`.

**Review what was drafted:** `workspace/drafts_review.md` (every drafted answer, with the fact ids it came from), or
`GET /api/drafts`. Presets the agent filled on the user's "draft ideal answers" instruction are listed in
`profile/presets.json` under `_drafted_by_claude_2026_10_07` (open_to_travel, plans_to_work_remotely).

**Answer waiting questions in the page:** `REGEN_API_WRITE=1 python -m uvicorn apps.api.main:app --port 8787` and
`cd apps/web && npm run dev`, open "waiting on you", type the answer. Then `python -m engine apply batches/requeue.json`.

## Next, in order
1. Workday / iCIMS adapters (most unresolved leads are there).
2. Engine room (GPU view), moved to v0.9.
3. pgvector retrieval memory; MCP tools for discovery and tailoring.
4. Companies that host their own Greenhouse-backed form: resume upload failed once on 10-07 (different DOM from the embed).

## What works
- Discovery: 4 ATS APIs, board registry, `watch`, new-grad and alert-email lead resolution.
- Fit gate: citizenship/ITAR, clearance, no-sponsorship, grad window, years, core stack.
- Tailoring: Fact-Bank-only, JD spelling, overlap groups, audit log (fact ids per resume).
- Apply: Greenhouse reliable; Ashby, Lever, Workable beta. Round-robin over tabs, drafted answers, airbags, proof.
- Feedback: inbox classifier, `learn`, verified-only `report`.

## Known gaps
- Single-choice "pick the best description" questions still go to you.
- Questions about citizenship country (export licensing) go to you by design.
- Ashby may flag automation; after a flag, Ashby submits pause for 24 h (`workspace/ashby_cooldown`).
