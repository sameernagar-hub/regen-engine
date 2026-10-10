# Handoff: v0.10 / v0.11 on main (2026-10-10, session in progress)

## When the user says "start" (do this first, in order)
1. Read this file + memory (`v1-direction`, `rejection-learnings`).
2. Start the API + web (control room): `.claude/launch.json` configs `regen-api` (REGEN_API_WRITE=1) and `regen-web`
   (local file, git-ignored), or:
   `REGEN_API_WRITE=1 python -m uvicorn apps.api.main:app --port 8787` and `npm --prefix apps/web run dev`.
3. Start continuous applying (Bash `run_in_background`):
   `REGEN_MAX_PER_DAY=60 REGEN_SKIP_ATS=workable python -m engine run --days 10 --max 60 --appliers 3 --tabs 3 --loop 20 > workspace/logs/loop_<date>.log`
4. Arm a Monitor on `workspace/codes/*.wait` (prints "CODE NEEDED: <file>") and keep a Gmail tab with
   `window.regenCodes` defined (see 10-10 session: searches `subject:(security code) newer_than:2h`, reads every code
   in each thread via the print view). Deliver with `python -m engine codes '<json>'` within a minute.
5. Inbox: search `label:jobs-rejections OR label:jobs-interviews newer_than:2d` (Gmail filters exist since 10-10),
   record with `python -m engine inbox <msgs.json>`, analyze each rejection's JD, add a rule + test, append to
   memory `rejection-learnings`.

## Priority queue (top = next). Keep this list current every time something lands.
1. **Keep the loop applying** + deliver codes fast (codes are the #1 cause of lost submissions).
2. **NEEDS YOU backlog (~96)**: answer box exists on the live page; build a bulk "answer once, apply everywhere" view
   in /control (group by question, POST /api/answers). Biggest completion lever after codes.
3. **MCP = the zero-cost cord**: add tools run_stop, filters_get/set, factbank, trust_check, priority_explain,
   inbox_record, outreach_draft (engine/connectors/mcp_server.py). No paid API keys, ever.
4. **Outreach**: recruiter / founder cold email drafts (FAANG, MANGO, AI labs, hiring YC founders) from Fact Bank only,
   saved as Gmail drafts; the user sends. LinkedIn connection invites only after the user approves a list.
5. **Docker appliers**: compose file with N applier services (one engine per container, shared workspace volume,
   own browser profile). User asked 10-10. Also free tools: local Ollama for zero-cost drafting (optional), uv.
6. **Sources**: SmartRecruiters public postings API; Workday/iCIMS assist list (user's accounts); Ashby reopens
   after `workspace/ashby_cooldown` + 24 h (a few per hour, it bot-flags bursts).
7. **Frontend**: assist list page (Lever captcha + Ashby filled forms, one click to open), outreach page, network
   graph (LinkedIn connections, read-only), job page shared-element morphs.
8. **Docs/v1**: README "By the numbers" refresh, CHANGELOG v0.10/v0.11 entries, wiki Security + Data-model +
   Benchmarks pages; docstrings sweep per docs/CODING_STANDARDS.md.

## Landed this session (10-10)
- Title gate: non-software disciplines dropped; defense JD blocker; slug-insensitive company exclusions.
- Forms: signature date, OPT/STEM/reserves from presets, home address, current employee/contractor, 5 days in person,
  "<metro> area", one-word acknowledgments.
- Selector: priority score + JD-match ordering, history (captcha-walled ATS, user-only blockers), one retry for
  code timeouts; scans merge into the queue; `--loop` first-applicant mode.
- Trust gate (ATS host allowlist + scam red flags, inbox scam detection).
- Web: /control, /applications (resume PDF + answers + facts + proof), /facts (Fact Bank map); v0.11 design layer.
- Gmail: 12 label filters (Jobs/...). Wiki: Zero-Cost-and-MCP, Trust-Gate, Job-Priority, Control-Room.
- Presets drafted by Claude on 10-10 (tell the user): `us_military_reserve: No`, `on_opt: Yes`, `stem_degree: Yes`.

## Needs the user
- Gmail app password in `.env` would make codes hands-free (`python -m engine codes --watch`).
- Arbitration (a game company), assessment link request, Lever captcha jobs and Ashby filled forms (assist list).

## Earlier

## State
- `main` = `v0.9` = 43a22e4 (fast-forward merges only; never merge on GitHub: it stamps a personal email).
- 28 verified submissions on 10-09 (`python -m engine report 2026-10-09`). All appliers stopped, no job waiting.
- Daily safety cap: default `REGEN_MAX_PER_DAY=25`; the user approved 40 for 10-09 (pass it per run, it is not in code).
- Ashby bot-check pause ends about **2026-10-09 23:22** (`workspace/ashby_cooldown` + 24 h). After that, Ashby leads
  (an AI lab and others) can go out again, a few per hour. queue.json was rescanned without Ashby: run a scan + `newgrad`
  + `alerts` again first so the Ashby leads are back in the queue.

## Resume here (in order)
1. Fix the title gate: "Transportation Engineering Leader" (a civil-engineering role) passed as software and was
   submitted. Require software context for "engineering leader/lead" titles (`engine/discovery/filters.py`,
   `profile/domains.json`), add a test, note it in the rejection log.
2. Run: `REGEN_MAX_PER_DAY=40 REGEN_SKIP_ATS=workable python -m engine run --days 2 --max 40 --appliers 3 --tabs 3`
   (launch with the Bash tool's run_in_background; a plain `&` in a finished shell got reaped once).
3. Codes: in the Gmail tab define `window.regenCodes` (reads every code in each thread, see the 10-09 session) or use
   `engine/discovery/gmail_codes.js`, then `python -m engine codes '<json>'`. Hands-free if the user adds a Gmail app
   password to `.env`: `python -m engine codes --watch`.
4. Big tech: `python -m engine bigtech 3` lists Amazon + NVIDIA roles with tailored resumes in
   `workspace/bigtech.md` (43 on 10-09). Those portals need the user's own account: the user submits.
   Not covered yet: Apple (search API returned nothing with the tried payload), Netflix (endpoint 404), Google and
   Meta (no public JSON API found). The AI lab in that group is on Ashby (normal pipeline).
5. Form gaps still seen: some Greenhouse "How did you hear" selects (one large API company), "Stay connected" SMS
   blocks (a life-sciences SaaS), an "ever employed by us" select left empty, Workable fill timeouts.
6. Docs: README was rewritten (Why REGEN, By the numbers, How it works) and the wiki now has 20 cross-linked pages
   (Home hub, Architecture, Discovery, Fit gate, Tailoring, Apply engine, Email codes, Outcomes and learning, Platform,
   Configuration, Metrics, Roadmap, sidebar and footer). Keep it current: when a subsystem changes, update its page,
   the Metrics table (from `engine report`) and the CHANGELOG in the same commit. Publish with the wiki clone:
   copy `docs/wiki/*` into a clone of `regen-engine.wiki.git`, commit, push. Next pages to add: per-ATS adapter
   pages, a data-model page with full event schemas, a Security page (threat model, privacy gate internals) and a
   Benchmarks page with charts.

## Environment gotchas
- Python: `%LOCALAPPDATA%\Programs\Python\Python314\python.exe` (the WindowsApps alias fails, including in
  the pre-push privacy hook: prepend that folder to PATH before `git push`).
- Git Bash heredocs turn `\b` into a backspace byte: write edit scripts with the Write tool; the control-char test catches it.
- Workable is bot-walling (pages time out / no confirmation). Lever shows hCaptcha on most jobs (left for the user).
- Gmail tabs freeze after long scripts: open a fresh tab.

## Needs the user
- Arbitration agreements (a game company: 2 roles). Online-assessment link request (same company).
- Self-certifications the engine won't make: "meet all basic qualifications", skill-specific years, export control,
  deferred compensation, legal-right-to-work proof wording.
- Lever hCaptcha jobs (forms filled, resumes ready): `python -m engine status`.
- Big-tech portal applications from `workspace/bigtech.md`.

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
