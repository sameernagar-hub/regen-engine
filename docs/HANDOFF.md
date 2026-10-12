# Handoff: v0.12 on main (2026-10-11 ~00:05)

## START HERE (10-12 morning): 5-minute checklist
1. Read this block + memory `regen-docker-bank`. Main = latest `git log -1` (all 10-11 work pushed).
2. Stack up? `docker ps --format '{{.Names}} {{.Status}}' | grep deploy` -> api, pipeline, relay, supervisor, applier-N.
   If not: `cd regen-engine && REGEN_MAX_PER_DAY=150 REGEN_TABS=4 docker compose -f deploy/bank.compose.yml up -d --scale applier=2`
   (the supervisor scales 1..7 by itself). Recreate, never restart, after a reboot (`--force-recreate`).
3. Health: `docker exec deploy-supervisor-1 python -m engine fleet` and `docker logs --tail 20 deploy-supervisor-1`.
   Expect "IMAP code watcher on" (codes are automatic now; no Gmail tab, no Claude needed).
   If the log says KILL: read the reason, inspect `workspace/quarantine/` (in the regen-workspace volume), then
   `docker exec deploy-supervisor-1 python -m engine supervise --clear`.
4. Numbers: `docker compose -f deploy/bank.compose.yml run --rm --no-deps --entrypoint python pipeline -m engine report 2026-10-12`
   (10-11 ended with 24+ verified).
5. Ashby: 250 queued jobs; the bot-check cooldown ends ~06:27 10-12; 1 Ashby job per pass (REGEN_ASHBY_PER_PASS).
   Watch for a new cooldown (`workspace/ashby_cooldown`); raise to 2 per pass only if none trips by noon.
6. Fresh supply each morning (in the pipeline container): `python -m engine hn 2`, `python -m engine boards harvest`,
   `python -m engine scan 7 --ats greenhouse,ashby,lever`, `python -m engine newgrad 7`, `python -m engine feed 7 --queue`.

### Tell the user first thing
- 32 cold-email drafts are in Gmail Drafts (nothing sent). Delete before sending: Duets (address looks malformed),
  Furtim Modus (agency), "Early-stage Startup" (personal gmail). User sends the rest themselves.
- /needs still holds legal-only questions (arbitration, export control, criminal history, citizenship without a
  preset, "do you have offers", credit history). 37 answers Claude drafted on 10-11 are in profile/answers.json with
  a `source` per entry; the user can review them on /needs or /facts.

### Build next (user's 10-11 asks, in priority order)
1. **Postgres ledger**: add a `postgres` service (named volume, 127.0.0.1 only, password from .env), point
   `apps/api/store.py` at it, migrate `events.jsonl` into labeled/normalized tables (applications, answers, codes,
   outcomes, supervisor audit, fleet heartbeats); keep events.jsonl as the append-only source of truth.
2. **MCP oversight** (engine/connectors/mcp_server.py): tools `fleet_status`, `kill(reason)`, `clear_kill`,
   `audit_log(n)`, `quarantine_list`, `scale(min,max)` so Claude can watch and stop processing at any step.
3. **Kill switch per step**: pipeline (scan/tailor/dispatch) and runner (before each submit) check `KILL` too, not
   only the supervisor and workers (`batches/STOP`).
4. **Guard stricter**: also scan resumes/proof text and outgoing outreach bodies before Gmail APPEND; block any
   draft containing presets-only data (address, phone, visa status) the user did not approve for outreach.
5. **Data hygiene**: retention policy (logs 14 d, proof 90 d, codes 1 d) in engine/clean.py run by the supervisor;
   label every event with `kind` + schema version; normalize company names (one slug function everywhere).
6. **More platforms**: SmartRecruiters adapter (public postings API, apply without account); daily `hn` + `outreach hn
   --gmail` inside the supervisor (dedupe contacts already drafted); "most active boards" ranking (postings/week
   from scan) to scan hot boards every pass and cold ones daily.
7. Gmail cleanup (user asked 3x): move code mail >1 day and job alerts >3 days to Trash via IMAP (COPY to
   [Gmail]/Trash), never empty Trash. Needs the user's OK for the exact search before running.

### Gotchas learned 10-11
- Git Bash heredocs turn `\b` into a backspace byte: write patches with the Write tool, then
  `grep -cP "[\x00-\x08]" file` must print 0.
- Privacy pre-push hook blocks company names, personal status words and example emails in code/docs: use
  placeholders ("<Co>", "a code bounced").
- Gmail threads code emails; IMAP reads single messages (use IMAP, not the Atom feed).
- `requeue.py` and the supervisor dedupe by role (company + title) and skip in-flight jobs: never requeue old
  batches by hand without them.

## 10-11 ~22:55 update: the supervisor runs the fleet
- `deploy/bank.compose.yml` now has `supervisor` (only service with the Docker socket, reads ../.env):
  autoscale 1..7 appliers (one per 3 jobs; clones a running applier to add, removes idle ones), requeues lost
  claims, prunes dangling images, audits every action (`supervisor` events), IMAP codes (app password in .env:
  REGEN_SMTP_USER / REGEN_SMTP_APP_PASSWORD; verified delivering), leak guard + kill switch (secret in a new
  log/outreach/ledger byte -> STOP + KILL, containers stopped, file to workspace/quarantine/). Clear after review:
  `docker exec deploy-supervisor-1 python -m engine supervise --clear`.
- Start everything: `REGEN_MAX_PER_DAY=150 REGEN_TABS=4 docker compose -f deploy/bank.compose.yml up -d --scale applier=2`
  (the supervisor grows it). Health: `python -m engine fleet` or `curl 127.0.0.1:8787/api/control/fleet`.
- 24+ verified on 10-11. Answers: 37 drafted into profile/answers.json (source per entry); right-to-work proof from
  presets; legal retry only when a preset answers. Ashby (250 jobs) cools down until ~06:27 10-12.
- Sources: HN "Who is hiring" (`python -m engine hn 3`): +71 boards, 160 published contacts. Outreach:
  `python -m engine outreach hn 60 --gmail` saved 32 drafts to Gmail Drafts (nothing sent). Flag to user: Duets
  (address looks malformed), Furtim Modus (agency), "Early-stage Startup" (personal gmail).
- NEXT (user asked 10-11, not started): Postgres for the ledger (apps/api/store.py supports it; add a `postgres`
  service + migrate events, labeled/normalized tables), MCP tools for Claude oversight (fleet, kill, clear, audit
  log), memory/data cleanup policy, SmartRecruiters adapter (public API, no account), run `hn` + outreach in the
  supervisor once a day.

## 10-11 ~21:45 update (v0.12.1 "Fleet", see CHANGELOG)
- Health first: `python -m engine fleet` (or `curl 127.0.0.1:8787/api/control/fleet`, or the Fleet panel in /control).
  The stack now has an `api` service; pipeline/appliers/relay heartbeat into `workspace/fleet/`.
- Codes are THE bottleneck (B5: 16.3/h with live codes vs 0.75/h without). The user's pasted relay tab froze twice
  and the fleet showed "Gmail tab silent". Fallback that works: Claude reads the Atom feed in its own Chrome tab
  (read-only JS) and POSTs `[{company, code, iso}]` to `127.0.0.1:8799/codes` with curl, driven by a Monitor on
  `codes_waiting`. Hands-free fix needs the user: a Gmail app password in `.env` (`engine codes --watch`), or Chrome's
  Memory Saver exception for mail.google.com.
- Lost claims after a container dies: `scripts/requeue.py --stale` (run in the pipeline container, see its docstring).
- v0.12 list left: Gmail cleanup (do it when no form waits on a code: the full Gmail UI froze tabs), SmartRecruiters
  source (needs an apply adapter to add volume), B5 by worker count.

## 10-11 ~20:25 update
- Stack restarted (it had been killed ~20 h earlier); now recreated with `--force-recreate` on a rebuilt image.
  Restarted (not recreated) appliers had no X server: stale `/tmp/.X99-lock`. The entrypoint now removes it.
- Landed (cf39afd): select() dedupes by company+title and seeds with submitted roles (a role went out twice; two roles were
  3x in one batch); a required form question saying "requires US citizenship" skips the job; B2 rules (own-city
  "based in", transitioning service member, contractor on behalf of, "legally eligible for employment").
- 3 verified on 10-11 at 20:24. Codes relay tab: Claude's paste into Gmail was blocked by the permission
  classifier; the user pastes `engine/discovery/gmail_relay.js` into the Atom-feed tab themselves.
- Next form gaps seen: "How did you hear about <co>?" select, multi-select locations / travel % / most recent
  education, "AI tools" single choice, onsite-city requirement.

## Start of next session (in order)
1. Read this file + memory (`regen-docker-bank`, `v1-direction`, `rejection-learnings`).
2. Stack should still be running: `docker ps` (deploy-pipeline-1, deploy-applier-1..5, deploy-relay-1). If not:
   `REGEN_MAX_PER_DAY=150 REGEN_TABS=4 REGEN_PARTS=5 docker compose -f deploy/bank.compose.yml up -d --scale applier=5`
3. Codes: Chrome tab on https://mail.google.com/mail/u/0/feed/atom/ with `engine/discovery/gmail_relay.js` pasted.
4. Numbers: `docker compose -f deploy/bank.compose.yml run --rm --no-deps --entrypoint python pipeline -m engine report <date>`.
   At handoff: **118 verified total, 46 on 2026-10-10** (best day), 2 so far on 10-11.
5. Benchmarks: `python scripts/bench_system.py` (needs the bank ledger copied to workspace/ or run in a container).

## Priority queue
1. Keep the stack applying; watch `docker logs deploy-pipeline-1 | grep report`.
2. B2 missing answers (67.5% of non-legal questions answerable): add rules for "currently based in <city>"
   (city-match), "transitioning service member" (preset No), "performing work on behalf of X as a contractor" (No),
   "legally eligible for employment in the US" (Yes). Re-run B2.
3. Gmail cleanup (user asked twice): move code emails >1 day and job-alert mail >3 days to Trash. Gmail's UI freezes
   tabs; try the basic-HTML view or a fresh foreground tab with a small batch. Never empty Trash.
4. Benchmarks B5 (submissions/hour by N), B6 (code latency), B7 (fit-gate precision).
5. Supervisor view in /control (container health + inbox/claimed/done counts), SmartRecruiters, Workday/iCIMS.

## Needs the user
- Local copies: `profile/` and `workspace/` are still on disk (stale; the bank is live). Backups verified at
  `../regen-backups/regen-profile-20261011.tgz` (12 entries) and `regen-workspace-20261011.tgz` (170 MB, has events.jsonl).
  Claude does not hard-delete user data: delete them yourself if you want them gone (keep `profile.example/`).
- /needs: legal / EEO / export / arbitration questions.
- Ashby cooldown started ~23:25 10-10; parked Ashby jobs return automatically after 24 h.

## v0.12 state (10-10 ~23:55): everything runs in Docker FROM THE BANK
- Stack: `deploy/bank.compose.yml` (named volumes regen-profile + regen-workspace; pipeline, applier x5, relay).
  Host `workspace/` and `profile/` are a STALE copy now: run reports in a container, e.g.
  `docker compose -f deploy/bank.compose.yml run --rm --no-deps --entrypoint python pipeline -m engine report <date>`.
  Git Bash: prefix `MSYS_NO_PATHCONV=1` on `docker run` with container paths.
- Codes: Chrome tab on https://mail.google.com/mail/u/0/feed/atom/ with gmail_relay.js pasted (posts to the relay
  container). Re-paste if the tab reloads.
- 10-10 total: 35 verified (+ a payments-company SWE submitted after midnight in the bank). 105 verified to date.
- User asked to delete local copies of profile/workspace: Claude does not hard-delete user data; the user deletes them
  after backing up the volumes (commands in bank.compose.yml header).

## (earlier) v0.12 state (10-10 ~23:40)
- Start: `REGEN_MAX_PER_DAY=150 REGEN_TABS=4 REGEN_PARTS=5 docker compose -f deploy/appliers.compose.yml up -d --build --scale applier=5`
  (pipeline + 5 appliers). Stop after current batch: `touch workspace/batches/STOP`; or `docker compose ... down`.
- Codes: `python -m engine relay` on the host + paste `engine/discovery/gmail_relay.js` into a signed-in Gmail tab
  (re-paste after the tab reloads). Check `workspace/logs/relay_*.log`.
- Ashby cooldown started ~23:25 10-10 (5 parallel workers tripped it); parked "not opened" Ashby jobs auto-return
  after 24 h; now max 1 Ashby per pass.
- Next: Gmail cleanup (move code emails >1 day and job-alert mail to Trash; user asked 10-10, never empty Trash),
  per-container supervisor view in /control (container health from `docker ps` + done/claimed counts), frontend
  pages for scale-out, SmartRecruiters source, outreach drafts into Gmail.

## Landed 10-10 evening (~22:10 to ~22:40)
- Inbox: "after careful consideration, we have decided" = rejection (a marketing-SaaS reject was read as a confirmation).
- Needs-you: 79 answers drafted from presets + Fact Bank (user: "draft them, don't ask"); 35 jobs requeued
  (`batches/requeue_2238.json`). Left for the user: legal/EEO/export/arbitration, captcha, Ashby human click.
- Forms: "Do you possess N years of experience in X" answered from the Fact Bank (No when N > years); STATUS_Q's
  `age` matched "language", which sent every programming-language question to the human queue (fixed).
- Tailor: coverage fill adds up to 2 Fact Bank skills lines for JD terms the page missed (median was 88% of the
  candidate's JD terms on the page; ATS read-back median 90).
- Sources: `newgrad 5` (+40 resolved) and `feed 7 --queue` (SimplifyJobs ATS rows) merged into queue.json.
- Title gate: Salesforce admin/consultant/analyst allowed (user: 5 certs). Fact Bank: Ruby, NoSQL added (user-stated).
- Outreach: 15 drafts in `workspace/outreach/drafts.md` (Gmail compose links; user adds recipient and sends).

## Priority queue (top = next). Keep this list current every time something lands.
1. **Keep the loop applying** + deliver codes fast (codes are the #1 cause of lost submissions; 11 of 10-10's
   submissions went through only because codes were delivered within a minute).
2. **Needs-you backlog**: /needs page is live (group by question, answer once, retry). Ask the user to spend 5 minutes
   there; `pipeline.answerable_now` re-queues jobs automatically when their questions become answerable.
3. **Outreach**: recruiter / founder cold-email drafts (FAANG, MANGO, AI labs, hiring YC founders) from Fact Bank only,
   saved as Gmail drafts; the user sends. LinkedIn connection invites only after the user approves a list. Add an
   MCP tool `outreach_draft` and a /outreach page.
4. **Docker appliers**: compose file with N applier services (one engine per container, shared workspace volume, own
   browser profile). Then the cloud plan below.
5. **Sources**: SmartRecruiters public postings API; Workday/iCIMS assist list (user's accounts); Ashby reopens after
   `workspace/ashby_cooldown` + 24 h (a few per hour; it bot-flags bursts).
6. **Frontend**: assist list page (Lever captcha + Ashby filled forms, one click to open), outreach page, network graph
   (LinkedIn connections, read-only), shared-element morphs between /applications and /job.
7. **Docs/v1**: CHANGELOG v0.10/v0.11 entries, wiki Security + Data-model + Benchmarks pages, docstring sweep per
   docs/CODING_STANDARDS.md, then tag v1.0 = "REGEN as an MCP connector/plugin" (user's release definition).

## Cloud plan (user, 10-10; not started)
The local machine becomes only the **knowledge source** (Fact Bank, presets, resumes, inbox access through the user's
AI client); everything else runs in containers: appliers (Docker, one engine per container), the API, and the event
store (Postgres; `apps/api/store.py` already supports it). Render serves the frontend and reads state from the cloud
API instead of the gh-pages feed. Open questions for the user: where containers run (Render background workers vs a
VM), how the Fact Bank syncs (encrypted, user-held key), and Gmail codes in the cloud (IMAP app password).

## Frontend = Render (10-10)
`https://regen-engine.onrender.com` (Render Blueprint, auto-deploys `main`, public mode). The gh-pages branch only
serves `replay.json` (the anonymized feed) and redirects to Render; publish with `python -m engine site 7 --push`
after a session. Repo homepage points to Render. Local-only pages show a "runs on your machine" panel in public mode.
Screenshots for the README: `python scripts/screenshots.py http://localhost:3000` (hides narration, names, logs).

## Landed this session (10-10, ~23:30 to ~01:00)
- 81 verified total (12 this session, 11 after midnight via live code delivery).
- Title gate: non-software disciplines; defense JD blocker; slug-insensitive company exclusions.
- Forms: signature date, OPT/STEM/reserves from presets, home address, current employee/contractor, 5 days in person,
  "<metro> area", one-word acknowledgments.
- Selector: priority score + JD-match ordering, history (captcha-walled ATS, user-only blockers), one retry for code
  timeouts, NEEDS YOU -> RETRY when answerable; scans merge into the queue; `--loop` first-applicant mode.
- Trust gate (ATS host allowlist + scam red flags; inbox scam detection).
- MCP v0.10 tools (run_start/stop, control_state, filters, factbank, trust_check, priority_explain,
  needs_by_question, answer_save, inbox_record).
- Web: /control, /applications (resume PDF + answers + facts + proof), /needs, /facts, shared nav everywhere, graph
  focus links, v0.11 design layer (neural-field backdrop, ViewTransition morphs, scroll-driven reveals).
- API write flag can live in `.env` (`REGEN_API_WRITE=1`); `.claude/launch.json` is local (git-ignored).
- Gmail: 12 label filters (Jobs/...). Wiki: Zero-Cost-and-MCP, Trust-Gate, Job-Priority, Control-Room; README
  rewritten for v0.10/v0.11 with new screenshots; docs/CODING_STANDARDS.md.
- Presets drafted by Claude on 10-10 (tell the user): `us_military_reserve: No`, `on_opt: Yes`, `stem_degree: Yes`;
  `profile/priority.json` tier lists (FAANG/MANGO/AI labs/big sponsors) are Claude's draft too.

## Needs the user
- Gmail app password in `.env` would make codes hands-free (`python -m engine codes --watch`).
- /needs: answer the non-legal questions; arbitration (a game company), assessment link request; Lever captcha jobs
  and Ashby filled forms.

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
