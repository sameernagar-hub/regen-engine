# Handoff: v0.9 (2026-10-09 midday)

## Resume here
- Branch `v0.9` (pushed, not merged; merge is the user's call, fast-forward only). 24 verified submissions on 10-09.
- Run: `REGEN_SKIP_ATS=workable python -m engine run --days 5 --max 40 --appliers 3 --tabs 3`. Workable pages time
  out / never confirm today (bot wall); Lever shows hCaptcha on most jobs (human queue).
- Ashby cooldown ends about 2026-10-09 23:22: then run the Ashby jobs (alert + feed leads are queued).
- Codes: still relayed from Gmail by hand unless the user adds a Gmail app password to `.env`; then run
  `python -m engine codes --watch` next to the appliers.

## Needs the user
- Arbitration agreements other than the approved one (a game company: 2 roles waiting).
- Self-certifications the engine won't make: "do you meet all basic qualifications", skill-specific years
  (e.g. "2 years with Terraform"), export-control questions, deferred compensation.
- Lever hCaptcha jobs (form filled, resume ready): listed by `python -m engine status`.
- Gmail app password (hands-free codes + IMAP inbox), new online-assessment link (game company).

## Earlier (2026-10-08)

- Branch `v0.9` (pushed, not merged). New this session:
  - **JD-first resume composer** (`engine/tailoring/compose.py`): headline = role + the 3 skill items the posting mentions
    most; summary = lane opener + best-matching user-written sentences (one voice); skills lines reordered JD-first;
    per-lane projects title; **ATS read-back** (pypdf text extraction, % of JD terms readable) logged per resume.
  - Fact Bank +14 facts, 3 projects, 6 skill lines from the user's own Zoox Embedded + Google SRE resumes; new
    `embedded` and `sre` lanes; embedded/firmware titles now allowed, CNC/machinist excluded.
  - Fit gate: JDs are HTML-unescaped first (hid "no sponsorship" etc.); grad window catches "degree by 2027".
  - Fixes: airbag `flag()` crashed (`kind` passed twice); referral-name rule (and not "preferred"); contractor,
    certifications, "closest location", "based in <city>", "learn about this opportunity", background-check wording.
  - **Engine room** (Next.js): `/room` (5 live rooms, SSE), `/room/[stage]` (live log, doors to linked rooms),
    `/job?u=` (full timeline: facts, coverage, ATS %, Q&A, proof). API: `/api/stations`, `/api/job`.
- Wave 2 apply (`run_20261008_2335`) may still be running; check `python -m engine report`.
- Codes: open a FRESH Gmail tab per lookup (old tabs freeze), read rows, `python -m engine codes '<json>'`.


## Next
1. Merge v0.9 (fast-forward), CHANGELOG entry, wiki page for the composer.
2. Gmail labels; dropdown/radio fill failures (SMS opt-in and onsite selects answered but left NEEDS YOU).
3. Engine room: animated flow between rooms on each event, resume preview per job.

## Older plan
## v0.9: tracked work, in order
1. **Ashby jobs after the bot-check pause** (ends about 2026-10-08 22:27): 14 queued Ashby jobs (alert-resolved and
   GitHub-feed), a few per hour.
2. **Gmail labels for every platform** (user request): `Jobs/Alerts/{LinkedIn ✅, Indeed, Glassdoor, ZipRecruiter,
   Monster, Ladders, Handshake}`, `Jobs/Codes`, `Jobs/Applications`, `Jobs/Rejections`, `Jobs/Interviews`. Driving
   Gmail's UI click by click stalls the tab; the faster routes are Gmail filters (auto-label new mail, need the
   user's OK because they are standing rules) or IMAP with an app password the user creates (labels via X-GM-LABELS).
3. **Inbox cleanup** (user request): move to Trash only the message types the user names. Never empty Trash.
4. **Form gaps still seen**: single-choice "which best describes your project", "how did you hear" selects without a
   careers option, acknowledgment checkboxes with long labels, "rate your proficiency" scales, EEO selects on some
   Greenhouse skins, resume upload on company-hosted Greenhouse pages.
5. **In-process overlap**: Playwright's async API, so browser round trips themselves overlap (today each applier is
   ~95% busy; parallel processes are what scale).
6. **Engine room**: GPU live view (instanced board field, glowing pipeline, 3D lane tree, render-on-demand).
7. **Retrieval memory**: pgvector over facts and job descriptions; MCP tools for discovery and tailoring.
8. **Workday / iCIMS adapters** (most unresolved leads are there; the user creates the account).

## Presets set on the user's instructions (2026-10-07)
Citizenship, street address, onsite, salary policy (posted-range midpoint, else `market_salary` 140000, an estimate
the user may change), and three drafted on "draft and move on": open to travel, plans to work remotely (No),
willing to do a background check. All are listed inside `profile/presets.json`.
