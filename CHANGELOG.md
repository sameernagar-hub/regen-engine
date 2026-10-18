# Changelog

Every change to the engine, newest first. Each entry says **what** changed, **why**, and **how to verify** it,
so a reviewer can check the work without reading the whole diff.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow the README roadmap.

## [1.0.0] - 2026-10-17 · first public release
- **Human draft override** (`engine/override.py`, `python -m engine draft on|off|status`; user, 10-17: "when I say
  draft, then draft"). While on, the engine answers instead of parking: agreements and arbitration accepted (the
  user's consent, logged), export-control / U.S.-person / sanctioned-country questions from the citizenship presets,
  pronouns declined, addresses from presets, open text force-drafted from the Fact Bank; every such answer is
  recorded on the job as `user override`, and parked jobs get one more try. Never, even when on: facts not on file
  (criminal record, vaccination, products used, immigration case...), human checks, EEO beyond a decline;
  `engine draft status` lists those. Verify: `tests/test_override.py`.
  First override pass: 62 selected (was 0-4), 8 of 48 submitted. Fixed from what it showed: the override never
  force-drafts a yes/no question (they go to the Fact Bank yes/no logic); "an understanding / knowledge /
  familiarity of X" counts like "experience with X"; "Do you live in one of the following states: ..." answers from
  your state preset; "Bachelor's ... plus N years" says No when N exceeds your years (it got "Master's").

- **Background facts from presets** (user, 10-18: "do not ask such questions"): criminal record, active immigration
  case, COVID vaccination and adverse credit are preset keys (`criminal_record`, `active_immigration_case`,
  `covid_vaccinated`, `adverse_credit`) with rules in the runner; parked jobs on them retry. An unset preset still asks.

Release review of every file. Fixes for what it found:
- **DNS rebinding on the API** (`apps/api/main.py`): CORS does not stop a page that re-points its own name at
  127.0.0.1; it could read every endpoint (Fact Bank, applications) and, in the bank, write answers.
  `TrustedHostMiddleware` now allows only `127.0.0.1`, `localhost` and the bank's `api` name (`REGEN_API_HOSTS`).
  Verify: `curl -H "Host: evil.example" 127.0.0.1:8787/api/health` -> 400; `tests/test_v1_security.py`.
- **Desk without a password** (`deploy/bank.compose.yml`): noVNC ran `-nopw`, and WebSockets skip CORS, so any web page
  could drive the desk browser where the user is signed in to employer portals. Each start now makes an 8-character
  random VNC password, stores it owner-only in the bank (`workspace/.desk_pass`), and `/api/reach/*` hands the control
  room a link that carries it. Verify: the RFB handshake offers security type 2 (VNC auth) only.
- **Code relay origin** (`engine/apply/code_relay.py`): any page could POST codes. Browser posts must come from
  `https://mail.google.com`; curl / IMAP (no Origin) still work; Host header checked. Verify: `tests/test_v1_security.py`.
- **Live view (7777) Host check** (`engine/live/server.py`), same rebinding hole as the API on the event feed.
- **Memory stack ports** (`deploy/docker-compose.yml`): Neo4j 7474/7687 and pgvector 5432 were published on every
  interface (your network); now 127.0.0.1 only like the rest.
- **Desk crash loop after a recreate**: the old container's Chromium `Singleton*` lock on the profile volume made the
  new desk exit 21 forever. The entrypoint clears it (one desk per volume). Verify: recreate the desk, it stays up.
- **Greenhouse resume upload** (`engine/apply/runner.py fill_gh`): two of the first ten forms of 10-17 stopped at
  RESUME UPLOAD FAILED; the proof shows Greenhouse's own `Cannot read properties of undefined (reading 'uploadFile')`.
  Retries now go 1) set the input, 2) the Attach button's file chooser, 3) reload then set the input.
- **Wrong answers on three real forms** (parked on other questions, so not submitted; `engine/apply/runner.py` RULES):
  "the country you are legally registered to work in" had no rule and got a drafted paragraph -> your country;
  "Describe your experience with X. Include ... years of experience" got the bare years number -> the years rule skips
  describe / explain / include prompts; "experience using AI coding agents (... GitHub Copilot)" got the GitHub URL ->
  link rules skip labels that ask about experience. Verify: `tests/test_v1_answers.py`.
- **Ashby "Location" that asks for a country** (8 forms parked on "Missing entry for required field: Location"): the
  field's description says "Country you're currently residing in" and its list holds countries only, but the city
  rule typed "San Jose, California". The description is now read; a country prompt gets your country. Verified on a
  live posting's DOM (read-only) and in `tests/fixtures/forms/ashby_country.html`.
- **"Are you wanting to work in person?"** parked: the onsite rule knew only "in-person"; now both spellings (your onsite preset).
- **A captcha was retried blind, and Ashby flagged it as spam** (seen live 10-17 22:32/22:39): Ashby showed a
  reCAPTCHA image grid after Submit; the engine logged "no confirmation seen (captcha?)", which is retryable, so it
  submitted the same form again 7 minutes later and Ashby answered "flagged as possible spam" (24 h cooldown). Now a
  visible challenge (reCAPTCHA grid, hCaptcha, Turnstile) during an Ashby or Greenhouse submit is `FAILED: CAPTCHA`
  for you to finish (never retried), an Ashby challenge starts the cooldown at once, and an Ashby "no confirmation
  seen" is never retried. Verify: `tests/fixtures/forms/ashby_captcha.html`, `tests/test_v1_answers.py`.
- **Closed postings were re-selected every pass** (`engine/tailoring/batch.py`): a 404 / job no longer on the board
  printed "posting is gone" but recorded nothing, so the same jobs took selection slots and fetches forever. They
  are now `SKIPPED` ("JD: posting is gone") and pruned; a network error still gets another pass.
- **More boards**: 7 more public job lists in `HARVEST_FEEDS` (probed 200 OK) and HN "Who is hiring" over 12 months
  (`engine hn 12`): Greenhouse 1,187 -> 1,233, Ashby 822 -> 928, Lever 381 -> 412, Rippling 164 -> 173.
- **Discovery window 30 days** in the handoff start command (was 7): one pass went from 5 to 28 selected jobs.
- **"Please do not use AI"** questions got a Fact Bank draft. The employer asked for the candidate's own words, so
  these now go to you (`NO_AI_Q`).
- **Supervisor could scale to zero appliers and never recover** (`engine/supervisor.py scale()`): a compose recreate
  racing the drain handshake left a drain on the last applier; it was retired, and new appliers are cloned from a
  running one, so none could be created again while a batch sat in the inbox (seen live 10-17 22:24). An applier is
  now retired only while `lo` other appliers are up (live heartbeat, not draining); otherwise its drain is cancelled
  and audited as `keep`. Verify: `tests/test_v1_security.py::test_scale_never_retires_the_last_applier`.
- **Dead heartbeats pile up** (~300 files in `workspace/fleet/`, one per recreated container): `engine clean`
  drops heartbeat files older than a day.
- **SECURITY.md** described a stack with one published port and one API write; it now lists every 127.0.0.1 port,
  who may write to it, and the root-run supervisor's limits.
- **Versions**: engine 1.0.0 (was 0.3.0 in pyproject), API 1.0.0 (was 0.8.0), web 1.0.0 (was 0.7.0); old
  `[Unreleased]` changelog entries numbered. README / wiki numbers refreshed from the ledger (191 submitted,
  5,471 boards on nine ATSs, 211 tests).

## [0.16.3] - 2026-10-16 · demo resumes + README screenshots
- **Resumes render on the public site**: demo resumes are one-page HTML pages (PDFs never enter the repo), `/proxy/*`
  allows same-origin framing (the site-wide `frame-ancestors 'none'` blocked it). Verify: Applications, pick a row.
- **Front page pitch** (0.16.2): headline, measured proof strip, demo note; two columns on desktop.
- **README screenshots** retaken from the live site: engine front page (hero), Control with a demo run, Needs you,
  Applications with the resume open, Live, Fact Bank.

## [0.16.0] - 2026-10-16 · "Front door": engine navigation + public proxy dataset
- **Engine front page** (`apps/web/app/page.tsx`, `engine.css`): a radial engine replaces the top tab bar; each
  part (cylinders, crankcase, fuel tank, ignition harness) opens a view, lights up with its live number on hover and
  zooms in on click. The old live view moved to `/live`; inner pages use a dock (`nav.tsx`). Why: the user asked for
  the engine itself to be the way in. Verify: open `/`, hover "Needs you", click it.
- **Proxy dataset** (`scripts/proxy_dataset.py` -> `apps/web/public/proxy/`, `apps/web/lib/proxy.ts`): the real API
  over a synthetic workspace + profile, snapshotted per route; public mode serves it and simulates writes in the tab.
  `LocalOnly` gates removed: Control, Applications, Needs you, Reach, Outreach and Fact Bank now work on Render.
  Why: the hosted site could not reach the Docker engine. Verify: `NEXT_PUBLIC_REGEN_MODE=public npm run dev`,
  answer a question on `/needs`; `python scripts/privacy_scan.py` stays clean.

## [0.15.0] - 2026-10-15 · supply + answers
- **Rippling auto-apply**: `ats.FILLED` + `APPLY_SUPPORTED`; pipeline scans rippling + jazzhr. Why: 161 boards, no
  account, no captcha seen; dry runs on two real postings filled every field. Verify: `tests/test_v015.py`.
- **Submit check**: Rippling submit ignores `[class*=error]` wrappers and the disabled/submitting state (two good
  submits were logged FAILED). Verify: proof screenshot shows the greyed form + spinner.
- **Discovery window** `REGEN_DAYS` (compose; was fixed at 1 day): one pass went from 0-1 to 20 selected jobs.
- **/needs**: the user's own legal / sponsorship answers are accepted and kept on that job only
  (`answers/job_extra.json` -> retry batch `extra`); EEO stays refused. "Apply now" works in the bank. Answered jobs
  whose batch file was cleaned are rebuilt from the ledger. Salary midpoint no longer skipped for jobs with extras.
  Verify: `tests/test_api.py::test_typed_legal_answer_stays_on_its_job`.

## [0.14.0] - 2026-10-14 · supervisor guardrails
The supervisor is the only container with the Docker socket, so whatever it creates runs with root-equivalent
reach on the host. Until now a cloned applier copied whatever limits its source had (none, if a container was ever
started without them), and nothing noticed a container in the project that compose never declared.

### Added
- **Bounded creates** (`engine/supervisor.py` `bound()`): every container the supervisor creates must be an
  allowlisted service (`SCALABLE` = applier), under `HARD_MAX` (12), never privileged, never with `CapAdd`, never with
  the Docker socket mounted, and gets CPU / memory / pids at or below the caps (`REGEN_APPLIER_CPUS` 1.5,
  `REGEN_APPLIER_MEM_MB` 2048, `REGEN_APPLIER_PIDS` 1024; missing or 0 = the cap). Labeled `regen.managed-by=supervisor`
  + `regen.created`. A refusal is audited (`supervisor` event, action `refuse`) once per pass.
- **Enforcement every minute** (`enforce()`): a running container of this compose project whose service is not in
  `DECLARED` is stopped and audited; a running applier without limits (or above the caps) gets them live via
  `docker update` (audited `bound`); a supervisor-made applier older than `REGEN_APPLIER_TTL_H` (12 h) is drained
  (audited `expire`) and an expiry drain is never cancelled by new work: a fresh applier is created instead.
- `containers.json` rows carry `managed` and `declared`.

- **Eval containers** (`evals()`, `engine/bench.py` B8-B10): benchmarks no longer run inside the supervisor. It
  creates one-shot `eval` containers (from the api container's config: image, bank volumes, Postgres secret, network;
  no ports, no write switches; 1 CPU / 1 GiB / 256 pids) when reposync pushed a commit not yet evaluated, when the
  last run is older than REGEN_BENCH_HOURS, or on `supervise --eval`; at most REGEN_MAX_EVALS (2), one launch per
  pass, the same trigger at most every 30 min; finished ones are reaped and audited with their exit code. New:
  **B8 supervisor** (7 decision scenarios on a faked Docker API: scale to backlog, drain before stop, never stop
  mid-form, stop after drain ack, refuse unsafe creates, caps, stop undeclared), **B9 api** (p50/p95 per endpoint),
  **B10 bus** (events.jsonl line -> Postgres row latency). Each run saves a summary and records an `eval` event, so
  the history is in Postgres; `GET /api/control/evals` returns it plus the running eval containers.
- **Workday filler + the desk** (`engine/apply/workday.py`, `desk` service): a headed Chromium with a persistent
  profile (volume regen-desk) served through noVNC at http://127.0.0.1:6080 (this machine only). The user signs in
  to a Workday tenant there once; `POST /api/reach/fill` (or `engine desk --fill URL`) queues a reach job, the desk
  walks Apply -> Apply Manually -> every wizard step by data-automation-id, fills from presets + Fact Bank, uploads
  the tailored resume, and stops at Review (submit is the user's click unless REGEN_WORKDAY_SUBMIT=1 and nothing was
  missing). A sign-in wall, a missing answer or a validation error goes to the user with the tab left open; a
  password field is never typed into. `GET /api/reach/desk` = desk heartbeat + latest result per URL.

- **SmartRecruiters in the desk** (`walk_sr`): the Easy apply form sits behind a DataDome bot check (an unattended
  browser gets "An error occurred"), so SmartRecruiters is filled only in the desk, where the user is present: a
  bot check goes to the user ("solve it, then press Fill again"), the engine never tries to get around it, fills
  from presets + Fact Bank, uploads the resume and stops before Submit. Verified live 10-14 up to the bot check.
- **Workday sign-in list** (`GET /api/reach/signins`, `POST /api/reach/open`, /reach "Workday sign-ins"): employers
  by open reach jobs (one account per tenant host); "Open in desk" opens that employer's site in the desk and
  presses Sign In. Only hosts on the list are accepted. Verified live: the Salesforce sign-in dialog opened.
- Workday sites for employees / contractors (internal, contractor, restricted, private posting, conversion) are no
  longer listed (7 rows hidden).

### Fixed
- Desk text pass now covers `type=email`, `tel` and `url` inputs.
- **Age question answered "No"** (`answer_for`): "Are you at least 18 years of age / old?" matched the years-of-
  experience rule (18 > preset years -> No) before the over_18 preset. 11 forms got "No", 3 of them were
  submitted (one was later rejected). The age wording now skips that rule; regression test for four wordings.
- **Resume must be attached before any submit** (`resume_in`): only the Greenhouse filler checked the upload; now
  every ATS stops with `RESUME UPLOAD FAILED` (not submitted) unless the page shows a file in an input, the file
  name, or the ATS's "Replace" / "uploaded" marker. The Workday filler refuses Review without an upload.

### Verify
- `pytest tests/test_v014b.py` (B8, B9 skip, history, eval triggers / reaping / max, Workday walk on a local
  look-alike: fill + stop at Review, submit when allowed, sign-in wall; age wordings; resume check).
- `pytest tests/test_v014.py` (DECLARED matches deploy/bank.compose.yml, caps, refusals, enforce, expiry drain).
- Live 10-14: after the rebuild the supervisor logged `bound deploy-applier-N {'pidslimit': 1024}` for all 6
  appliers; `docker inspect` shows 1.5 CPU / 2 GiB / 1024 pids; an applying applier uses ~225 pids.

## [0.13.0] - 2026-10-13 · "Reach"
Most new-grad leads that never resolved pointed at Workday, iCIMS or SmartRecruiters boards, and the engine could not
see those ATSs at all. The fleet's containers were only visible through heartbeats, and the B5-B7 benchmarks only
ran when someone typed the command.

### Added
- **Three new discovery adapters** (`engine/discovery/ats.py`): `smartrecruiters` (public Posting API, US only, 100
  per page), `workday` (the public `cxs` search JSON the careers page calls itself, 20 per POST, stops at the first
  page with postings older than 7 days) and `icims` (portal search HTML, since iCIMS has no public JSON). iCIMS lists
  no posted date, so `posted` is the first time the engine saw the job: the first fetch of a board marks every open
  job as old, so it doesn't flood the queue. JDs come from the posting API, the cxs detail call, and the job page's
  JSON-LD. `ATS = OPEN_ATS + REACH`, and `SLUGGABLE` keeps newgrad from guessing slugs for Workday/iCIMS tokens.
- **Harvest** finds these boards in the public lists and in the local `leads.json` / `alert_leads.json` (no network
  calls). First run: 1,952 Workday, 295 SmartRecruiters and 278 iCIMS boards.
- **Reach list** (`engine/discovery/reach.py`, `python -m engine reach [max]`): Workday and iCIMS put the form
  behind a candidate account, so the engine does everything up to the click. That covers the title filter, fit gate,
  trust gate and tailored resume (`batch.build`). Each job becomes one row in `workspace/reach.json` + `reach.md`.
  The pipeline runs it after every scan (`REGEN_REACH_PER_PASS`, default 12, newest first), and `select()` leaves
  these ATSs out of apply batches. First run: 7 of 12 listed, 5 gated (years, stack, no sponsorship).
- **Supervisor container view**: `supervisor.inventory()` polls the Docker API (state, uptime, CPU %, memory/limit
  from one stats sample each, 8 threads) once a minute, off the 15 s loop. It writes `workspace/containers.json`, and
  `GET /api/control/containers` and the fleet status return it. The API never gets the socket. /control has new
  **Containers**, **Reach list** and **Benchmarks** cards.
- **Benchmarks in the bank**: `scripts/bench_system.py` moved to `engine/bench.py` (`python -m engine bench
  --save`; the script is now a thin wrapper) because the images don't ship `scripts/`. The supervisor runs it in a
  subprocess 5 min after start and every `REGEN_BENCH_HOURS` (6). It has to be a subprocess because B3 swaps the
  worker dirs. Results go to `workspace/bench/<stamp>.json` + `latest.json`, served by `GET /api/control/bench`.

### Fixed (10-13 rejection review)
- **Inbox classifier missed 30 rejections.** It read the first 1,500 raw MIME bytes from INBOX only, so the deciding
  sentence ("unfortunately", "will not be moving forward") was usually base64/quoted-printable or filtered out of the
  inbox. Now: decoded text/plain (or stripped HTML) from All Mail via a Gmail search, more rejection wordings, and
  "if you are not selected..." stays a confirmation. A re-read can correct a message (latest per msg_id wins; a
  `void` outcome retracts) in `events.read` and the Postgres `outcomes` view. Own sent mail and newsletters are never
  outcomes; company is matched on sender + subject before the body.
- **Fit gate, from 39 engine rejections:** "N+ years in <field>" counts as a years requirement (a 7-year lead role
  got through); a "sales track" blocker (years of pre-sales / solutions engineering / customer success); admin,
  consulting and sensor-integration titles are not engineering roles; one role posted per region is one role
  (`role_key` drops region suffixes: three regional copies got three rejections). B7 on the bank: catch rate 9.1% ->
  18.2% of rejections with a stored JD, at a cost of 2.2% of not-rejected submissions (was 1.1%).
- **Discovery:** LinkedIn alert mail over IMAP (`alerts --imap`, hourly in the supervisor as the engine user).
  Ashby forms: region-only location search, radio groups outside field entries, "If other" boxes never drafted.
  Greenhouse: the Employment block is filled from the Fact Bank's current role.

### Verify
- `python -m pytest -q` (157 passing; `tests/test_v013.py` fakes every HTTP call: harvest patterns, Workday paging
  stop, iCIMS first-seen dates, SmartRecruiters mapping, reach pick/write, CPU/mem math, inventory staleness, bench
  save, the three API routes). Live: `docker exec deploy-supervisor-1 python -m engine reach 12`, then open
  http://127.0.0.1:3000/control.

## [0.12.2] - 2026-10-12 · "Ledger"
The ledger lived only in events.jsonl: every question about it (submissions per day, answers by source, supervisor
actions) meant a script. Now the bank stack keeps a labeled Postgres copy next to it.

### Added
- **`postgres` + `ledger` services** in `deploy/bank.compose.yml` (named volume `regen-db`, 127.0.0.1:5433 only).
  The password is a Docker secret from the git-ignored `.pg_password` file, never an env var, so the API does not
  see the Gmail app password in `.env`. `ledger` runs `python -m apps.api.migrate --loop 15`: only new whole lines
  after a byte offset, still idempotent by sha256, offset advanced only after the commit.
- **Labeled relations**: `events` gains a schema version column `v` (1 when absent); views `applications`
  (company, title, status, proof...), `answers`, `codes`, `outcomes`, `resumes`, `discoveries`, `supervisor_audit`;
  table `fleet_heartbeats` (latest heartbeat per container). events.jsonl stays the append-only source of truth and
  the `events` table still refuses UPDATE/DELETE.
- **MCP oversight** (`engine/connectors/mcp_server.py`): `fleet_status`, `kill(reason)`, `clear_kill`, `audit_log(n)`,
  `quarantine_list`, `scale(min, max)`. They run `python -m engine supervise --status|--kill|--clear|--audit|
  --quarantine|--scale` inside the supervisor container through `docker exec`, because the host's `workspace/` is a
  stale copy and the bank lives in volumes. `kill` is always allowed (stopping is safe); `clear_kill` and `scale`
  need `REGEN_MCP_WRITE=1`. `scale` writes `workspace/fleet_limits.json` (hard cap 12, `0 0` parks the fleet), which
  the supervisor re-reads every pass. `python -m engine fleet --json` prints the same status.
  Verify: `docker exec deploy-supervisor-1 python -m engine supervise --status`; `pytest -k control_verbs`.

- **Kill switch per step**: `safety.killed()` reads `workspace/KILL`; `stop_requested()` honors it as well as `STOP`.
  The runner checks again right before each submit click (a filled form is left as `STOPPED`, nothing sent); the
  pipeline checks before scan, build and dispatch (`pipeline` event with `halted`), and its loop holds while killed.
  `supervise --clear` restarts the pipeline container that `kill()` stopped.
  Verify: `pytest -k kill_switch_reaches_every_step`.

- **Stricter leak guard** (`engine/guard.py`, shared rules): the supervisor scan now also covers resume specs
  (`specs/`) and the extracted text of each new or changed resume PDF (`out/`). Outreach drafts pass
  `guard.outreach_problems` before the Gmail APPEND: secrets, the preset phone, street address, salary numbers and
  work-authorization status words are blocked unless the key is in `presets["_outreach_allowed"]`; a blocked draft
  is not saved and leaves a `flag` event (`outreach_guard`) naming the rule, never the value. The 32 drafts saved on
  10-11 all pass. Proof screenshots are PNG only and are not text-scanned.
  Verify: `pytest -k "outreach_guard or guarded_drafts"`.

- **Data hygiene**: retention per the user's 10-11 policy (proof 90 d, logs 14 d, codes 1 d; resumes 3 d, JDs 14 d
  unchanged; each overridable with `REGEN_KEEP_<NAME>_DAYS`), run hourly by the supervisor instead of every
  pipeline pass. Every new event carries `"v": 1` (`events.SCHEMA_VERSION`). One company comparison everywhere
  (`engine/names.py`: `company_slug`, `role_key`): selection dedupe, per-company caps, blocked companies,
  in-flight jobs, requeue, the daily per-company rate airbag (was a prefix match: "Acme" counted "Acme Robotics")
  and email-code matching. Display names are unchanged.
  Verify: `pytest -k "slug or day_old"`.

- **Daily HN + outreach in the supervisor**: after 07:00 (`REGEN_DAILY_HOUR`) once a day, `hn 2` then
  `outreach hn 20 --gmail --new` (`REGEN_OUTREACH_PER_DAY`): Gmail drafts only for contacts that never got one
  (`outreach` events; the 10-11 drafts are backfilled once). Nothing is sent. Skipped while killed; audited as `daily`.
- **Hot boards**: every scan records postings-per-week per board (`workspace/board_activity.json`); the pipeline's
  short loop passes run `scan --hot` (boards that posted this week + any not fetched for 24 h).
  Verify: `pytest -k "daily or drafted or hot_boards"`.

- **`web` container** in the bank stack (`regen-web:local`, 127.0.0.1:3000): the control room no longer runs on
  the host. The supervisor probes `api` and `web` over HTTP and `ledger`/`postgres` by container state every
  minute, restarts one after 3 failed probes (audited `restart`), and reports them in its heartbeat; failures show
  as fleet problems.
- **Control room Fleet panel**: kill-switch banner, service health, ledger backend, applier limits, IMAP codes,
  only live members, and the supervisor's audit trail (`/api/control/fleet` now returns status + audit + ledger).

- **Data bus, no proxy**: the ledger's inserts fire `NOTIFY regen_events` (statement-level trigger); `/api/stream`
  LISTENs on it when the backend is Postgres, so a new event reaches the browser in ~1 s (ledger loop now 2 s)
  without polling. The web container no longer rewrites `/api` through itself: the browser calls the api container
  directly (`NEXT_PUBLIC_REGEN_API`, CORS limited to the web origin, CSP `connect-src`/`img-src`/`frame-src` name it;
  resumes carry `frame-ancestors` for the web origin).

- **`reposync` container** (`engine/reposync.py`): every 15 min rebuilds the anonymized feed from the bank and pushes
  gh-pages when it changed (Render stays live); local `main` commits not on GitHub are checked in a clean worktree
  (privacy scan with the real terms + full test suite) and pushed to `bot/sync` with a PR to main. Guardrails: push
  allowlist (gh-pages, bot/* only; main raises before git runs), force only as a lease on bot/*, no pushes while
  killed, diverged history reported not fixed, token only from the `gh_token` secret as a per-command header and
  scrubbed from every message. Heartbeats like every member; audited as `reposync` events.
  Verify: `pytest -k reposync`; `docker logs deploy-reposync-1`.

- **Answer queue + `answers` container** (`engine/feedback/answer_queue.py`): in the bank, `/needs` answers are
  validated by the API (legal/EEO/sensitive still refused) and queued in `workspace/answers/inbox/`; the `answers`
  container claims each one, saves it to profile/answers.json and drops one retry batch in `batches/inbox`, which the
  supervisor scales appliers for. Submitted jobs are skipped; held while KILL is on; `answer_queued/applied/refused/
  retry` events. The bank API gets an answers-only write switch (`REGEN_API_ANSWERS`), nothing else.
  Verify: `pytest -k answer_queue`.

- **Every local port explains itself**: `127.0.0.1:8787/` (and `/db`) is the API's own page: a request tracker
  (hits, errors, latency per route) and a live database browser over the Postgres ledger (every table/view with row
  counts, search, column filters, sort, auto-refresh on the data bus, CSV/JSON download; allowlisted relations,
  bound parameters only). `127.0.0.1:8799/` shows jobs waiting on a code (never code values), `/status` as JSON.
  The control room nav links "Data". Postgres (5433) speaks its own protocol, so its browser is the API page.

- **MCP at every level**: `mcp` container serves the MCP server over streamable HTTP at 127.0.0.1:8790/mcp
  (`.mcp.json` `regen-bank`; DNS-rebinding protection, localhost hosts only). Inside the bank the fleet verbs run
  in-process (kill writes the kill files every step honors); new tools `ledger_tables`, `ledger_rows`,
  `answer_queue_add` (needs REGEN_MCP_WRITE), `answer_queue_status`, `reposync_status`. The supervisor probes it.

### Fixed
- **Answers from /needs never reached the containers**: the bank API was read-only (and saw the browser as the
  Docker gateway, not 127.0.0.1), and `requeue()` wrote `batches/requeue.json`, which no container reads, after
  searching only top-level batch files (container batches live in inbox/claimed/done).
- **Fact Bank page blank**: one Fact Bank source was a plain line (facts added from chat) and `/facts` crashed on
  `added.length`; the API now returns every source as `{date, file, added}`.
- **Memory graph going deeper**: rings were a fixed list, so every layer past the 4th stacked on one circle; radius
  now grows with depth. Busy nodes (a Fact or ATS links 100+ applications) open their first 40 and report the rest,
  and the adjacency map is built in O(E) instead of copying a list per edge (a deep click froze the page ~1 s).
- `app/error.tsx`: a page that throws shows the error with a retry button and the nav, not a blank page.
- reposync's first live pass: one multi-ref fetch failed on the not-yet-existing bot branch and left `origin/main`
  stale (pushed commits looked local), and the feed push named `HEAD` of the main clone instead of the pages
  worktree (git rejected it as non-fast-forward). Fetches are per ref (main and gh-pages must succeed) and every push
  takes an explicit commit id (`HEAD` is refused by the guard).
- **Live narration never streamed**: clients open `/api/stream?after=999999999` for "only new events", but the
  server compared ids against that number literally, so only snapshots arrived. `after` is clamped to the newest id.
- A job whose page never renders its form (`ERROR`) is retried once, then treated as FAILED: one Ashby posting
  took the single Ashby slot of every pass.
- **The supervisor killed an applier mid-batch** (10-12 22:21): it chose an idle applier from a "watching"
  heartbeat, then `docker stop -t 20` gave the worker 20 s in which it claimed a fresh 3-job batch and died holding
  it. Retiring is now a handshake: `fleet/drain_<host>` -> the worker checks it before every claim and beats
  "draining" -> only then stop + delete. New work cancels pending drains before adding containers.
  Verify: `pytest -k drain`.
- A kill only reached workers between batches: `stop_requested()` looked at `workspace/STOP`, while `kill()` writes
  `KILL` and `batches/STOP`, so a running applier kept submitting until its batch ended.
- `engine fleet` no longer reports "Gmail tab is not posting codes" while the supervisor's IMAP watcher delivers
  codes (the supervisor heartbeat now carries `imap`).

- The `api` service reads Postgres (`/api/health` -> `"backend": "postgres"`).
  Verify: `docker exec deploy-postgres-1 psql -U regen -c "select date(ts), count(*) from applications where
  status='SUBMITTED' group by 1 order by 1 desc"`; `pytest tests/test_api.py -k "dsn or migrate"`.

## [0.12.1] - 2026-10-11 · "Fleet"
Completion, not supply, was the limit: one pass stopped 12 of 12 jobs on choice questions the engine could already
answer, and B5 showed the same 5 appliers drop from 16.3 to 0.75 submissions per active hour when the Gmail tab froze.

### Added
- **Fleet supervisor** (`engine/supervisor.py`): pipeline, appliers and relay write heartbeats to
  `workspace/fleet/`; `GET /api/control/fleet`, a Fleet panel in `/control` and `python -m engine fleet` show who is
  up, the batch queue, lost claims, codes waiting and whether the Gmail tab still posts. No Docker socket in containers.
  Verify: `curl 127.0.0.1:8787/api/control/fleet`; `pytest -k fleet`.
- **`api` service** in `deploy/bank.compose.yml` (127.0.0.1:8787, read-only): the control room reads the bank.
- **Benchmarks B5-B7** (`scripts/bench_system.py`): submissions per active hour, code latency (`code` events), fit
  gate vs rejections. Results in docs/wiki/Benchmarks.md.
- **`scripts/requeue.py`**: requeue open jobs after a fix; moves claims lost with a dead container to `batches/stale/`.

### Fixed
- Option matching (`runner.option_fallback`): "<Co> Career Site" for the careers-page answer, "Masters's Degree",
  travel-percent buckets, sponsorship and acknowledgment sentences, "commutable to our offices", "which best describes".
- One posting under several URLs went out up to 3 times; jobs already submitted or in a worker's batch are skipped.
- A required form question saying "this role requires US citizenship" now skips the job (the JD was silent).
- Arbitration clauses that only say "any disputes" mark the company as user-only.
- Restarted appliers had no X server (stale `/tmp/.X99-lock`); the entrypoint removes it.
- The relay unescapes `&amp;` in company names (a code for "A &amp; B" never matched "A & B").

## [0.12.0] - 2026-10-10 · "Scale-out"
Supply, not speed, was the limit: of 229 queued jobs only 17 were fillable. This release widens discovery, ranks fresh
jobs first, and adds container appliers so capacity is a number you set.

### Added
- **Container appliers** (`deploy/applier.Dockerfile`, `deploy/appliers.compose.yml`): one engine worker and one
  headed Chromium (on Xvfb) per container. `python -m engine worker` claims batches from `workspace/batches/inbox`
  with an atomic rename, so exactly one worker wins each batch, no broker needed. Scale with
  `docker compose -f deploy/appliers.compose.yml up -d --scale applier=N`.
  *Verify:* `test_worker_claims_each_batch_once`.
- **Hybrid dispatch:** `REGEN_DOCKER_PARTS=K` sends K batch parts to container workers while local appliers take the
  rest; one selector feeds both, so no job is applied twice. `REGEN_APPLIERS=docker` sends everything to containers.
- **Hands-free email codes without an app password:** `python -m engine relay` (loopback only) plus
  `engine/discovery/gmail_relay.js`. A signed-in Gmail tab reads the Atom feed every 20 s (one fetch, no UI, so no frozen tabs)
  and posts codes to the relay, which writes them only for waiting jobs.
- **Freshness bands:** jobs posted within the hour, then the day, then the week; older postings stay cold and are used only
  when hotter bands are empty. Picking k jobs uses a lazy heap: O(Q) heapify plus O(log Q) per pick, so there's no
  full sort. *Verify:* `test_select_prefers_fresh_band`.
- **Onsite preference:** onsite or hybrid roles rank above remote ones (+3 Bay Area, +2 elsewhere); remote roles are still applied to.
- **Queue prune:** jobs that can never be applied to (final status, skipped or captcha-walled ATS) leave the queue.
- **Resume coverage fill:** JD terms you have but the page doesn't show pull in up to two more of your own Fact Bank
  skills lines (median coverage was 88%; never invented wording).

- **System benchmarks** `scripts/bench_system.py`: B1 select (heap vs sort), B2 answer coverage over every question
  ever asked, B3 exactly-once claims under a race, B4 resume coverage. See wiki Benchmarks, Efficiency, Evidence.
- **MCP in every container** (`docker exec -i <container> python -m engine mcp`); **data bank** in named volumes.

### Fixed
- **Duplicate claims on Windows:** B3 found 233 claims for 200 batches with rename-only claims. Claims now use an
  exclusive lock file (O_CREAT|O_EXCL): 200/200 in 3 of 3 runs.
- `STATUS_Q` matched "age" inside "language": every programming-language question went to the human queue.
- "Do you possess N years of experience in X" is answered from the Fact Bank (No when N exceeds your years).
- Dropdowns that list the country as "US" now match "United States".
- An inbox snippet "after careful consideration, we have decided" is a rejection, not a confirmation.
- `.wait` files written in the Windows code page no longer crash the code matcher.

## [0.9.1] - 2026-10-09 · "Fewer stops"
Found while applying: each fix came from a form that stopped a real application. 24 verified submissions on 2026-10-09.

### Fixed
- **Sponsorship safety:** an H-1B history rule matched "require sponsorship (e.g., H-1B visa)" and answered No. It was
  caught before any submit (audit: no past submission ever answered a sponsorship question No); the rule now matches
  only "have you held H-1B / petition approved". *Verify:* `test_new_rules_2026_10_09`.
- **"N or more years of experience?"** is answered from your total years only when the question is generic; a
  skill-specific one ("2 years with AWS and Terraform") is never claimed from total years. *Verify:* `test_years_rule_is_generic_only`.
- **One oversized resume no longer stops the whole pipeline:** the composer drops the least relevant project and
  retries, and a resume that still won't fit skips just that job.
- **Email codes:** a three-minute margin for round-robin delay; one code per waiting job (oldest waiter first); a code
  a job already bounced is never sent to it again (two applications to one company can thread both codes together).
  *Verify:* `test_codes_one_per_job_and_skip_bounced`.
- SMS opt-in labels that mention email, "Have you worked at X?", "currently an X employee", "legally eligible to start",
  yes/no clauses inside a longer sentence, acknowledgement checkboxes that mention compensation, "(City, State)".

### Added
- `python -m engine codes --watch`: hands-free codes over read-only IMAP (needs a Gmail app password in `.env`).
- Salary dropdowns with range buckets: the computed salary picks the bucket that contains it.
- Derived answers: time-zone questions and "able to start within N days" from your presets.
- Presets (yours, git-ignored): work authorization status and its dropdown spellings, unrestricted authorization (No,
  time-limited), H-1B history, future opportunities.
- `REGEN_SKIP_ATS=workable` for the pipeline while an ATS is bot-walling; federal contractors excluded by default.

## [0.8.0] - 2026-10-07 · "Throughput, truthfully"
The goal for v0.8: at least 10 applications a day with less waiting, and no new loopholes. Every item lists how to check it.

### Added
- **Round-robin scheduler** (`engine/apply/scheduler.py`). An application spends most of its time waiting for the site
  (resume parsing, autocomplete, submit confirmation, email codes). Each job is now a generator in its own tab that
  `yield`s at every field (a checkpoint) and every wait. A job runs until its time quantum is used up (preempted, back of
  the ready queue) or it starts waiting (sleeps on a heap until its wake time), so the other tabs keep working.
  Pick O(1), preempt O(1), block/wake O(log S); only `REGEN_TABS` tabs are open (default 3).
  *Verify:* `python scripts/bench_scheduler.py 20 3` (seeded simulation from the real flows): 500 s → 244 s,
  144 → 295 jobs/h, browser busy 29% → 60% (x2.05); 40 jobs on 4 tabs: x2.50. `tests/test_v08.py::test_rr_*`.
- **Adaptive quantum per ATS.** EWMA mean and variance of each ATS's CPU bursts (West's one-pass update, O(1) memory);
  quantum = mean + 0.84 σ (80th percentile, the textbook RR rule), clamped to 2–20 s, persisted in
  `workspace/sched_stats.json`. *Verify:* `test_quantum_ewma_and_clamp`.
- **Company interleaving.** A batch is reordered round-robin over companies, so the per-company cap and Ashby's bot
  checks see spread-out traffic. *Verify:* `test_interleave_spreads_companies`.
- **Drafted answers instead of waiting** (`engine/apply/drafts.py`, user decision 2026-10-07). Open-ended questions
  ("Why us?", "Describe a time…", "What have you built?", "How do you use AI?") are answered with sentences built only
  from Fact Bank entries the job's tailored resume already chose ("Built X" → "At Acme, I built X"). No LLM, no network.
  Never drafted: sponsorship, authorization, arbitration, EEO, salary, sensitive data. Every draft is in the event log
  (`drafted`: question, answer, fact ids) and in `workspace/drafts_review.md`. *Verify:* `test_draft_*`.
- **Experience questions from the Fact Bank.** "Do you have experience with X?" is answered "Yes" only when X (or what it
  means, e.g. single-page apps → React) is in your skills; otherwise it goes to you, never a guessed "No".
  "Which of these have you used? Select all" ticks only the options your skills name.
- **Answer from the page** (v0.8 roadmap item). `POST /api/answers` saves an answer to `profile/answers.json` with its
  source, logs an `answer` event and re-queues the job (`batches/requeue.json`). Off unless `REGEN_API_WRITE=1`,
  localhost only, legal/EEO/sensitive questions refused. `GET /api/human` lists each job's unanswered questions;
  `GET /api/drafts` lists what was drafted. The live view's "waiting on you" panel has an answer box per question.
  *Verify:* `tests/test_api.py`.
- **Greenhouse codes for several jobs at once.** Each waiting job has `codes/<board>_<id>.wait`;
  `engine/discovery/gmail_codes.js` reads codes from Gmail rows and `python -m engine codes '<json>'` writes a code only
  to the job whose company the email names. *Verify:* `test_codes_only_go_to_the_named_company`.
- **Autofill policy: no manual stops** (user decision 2026-10-07: "no manual input, just draft and fill").
  Yes/no capability questions ("Have you shipped…", "Did you attend…") → Yes only when a Fact Bank entry backs it,
  otherwise No (it can understate you, it never claims something unproven); willingness questions → the presets'
  onsite/relocation stance; any non-sensitive text box → a Fact Bank draft, rotating facts within a job; single-choice
  questions → the option sharing the most skill terms with the drafted facts; "lived in the US N of the past M years" →
  computed from Fact Bank dates; date boxes for "start date" → the date your notice period lands on. Status questions
  (sponsorship, citizenship, sanctions, salary, EEO, criminal history, relatives, prior employment) are never defaulted.
  `REGEN_AUTOFILL=0` turns it off. *Verify:* `test_autofill_policy_*`, `test_us_years_*`, `test_best_by_overlap_*`.
- **Non-blocking field helpers.** `set_field` / `set_gh` are generators too, so dropdown searches and autocomplete waits
  yield to other tabs, and typing has no per-key delay. A run before this logged 949 s active of 957 s wall: the tabs
  were barely overlapping because the waits were inside these helpers.
- **Orchestration pipeline** `python -m engine run [--days --max --appliers --tabs --no-scan --dry]`
  (`engine/pipeline.py`): discover → select (never-tried jobs, ≤3 per company, interleaved) → build (JD fetches in
  parallel threads) → apply (the batch split across P applier processes, each with its own browser profile and T
  round-robin tabs) → report. Every stage logs a `pipeline` event.
- **MCP orchestration tools**: `pipeline_status` (live applier results, jobs waiting for a code, verified today),
  `pipeline_run` and `submit_codes` (both need `REGEN_MCP_WRITE=1`).
- **GitHub job lists into the queue**: `python -m engine feed 3 --queue` parses ATS, board and id from each
  SimplifyJobs posting URL and merges the Greenhouse / Ashby / Lever / Workable ones into `queue.json`.
- **Salary from the posting** (`engine/tailoring/salary.py`, user policy): the batch builder records each posting's pay
  range ("$135,000 to $164,000", "$135K-$164K"; hourly figures ignored) and salary questions get its midpoint as plain
  digits; with no range, the `market_salary` preset. *Verify:* `test_salary_*`.
- **Citizenship and address from presets** (user facts, 2026-10-07): "country of citizenship", "Are you a U.S. citizen?",
  "citizen or resident of any of the following countries: ..." (answered by checking the list against your
  citizenship and US residence), and "Address Line 1".
- **More alert sources**: `gmail_alerts.js` reads Monster ("Title" / "Company - City - ST" / "VIEW JOB" or "QUICK APPLY")
  and Ladders (two layouts) alerts. Jobot is skipped: it is a staffing agency and its alerts don't name the employer.
- **Gmail label** `Jobs/Alerts/LinkedIn` created and applied to existing LinkedIn alert mail (first of the per-platform
  labels; the rest are tracked for v0.9).
- **Multi-select skills dropdowns**: "Which X have you worked with?" picks only options your Fact Bank skills name.
- **Evidence tooling.** `scripts/bench_tailor.py` (old vs new tailoring: identical output, speed), `scripts/bench_scheduler.py`,
  headless Playwright tests of the real filler against local Greenhouse / Ashby / Lever look-alike forms
  (`tests/test_forms.py`), coverage in CI.

### Fixed (all seen on 2026-10-07)
- **Event log corruption.** The batch builder and the applier appended to `events.jsonl` at the same time; on Windows,
  append mode is "seek to end, then write", so two records were overwritten mid-line and every later job in the Ashby
  batch crashed with `Expecting value`. Writes now hold a cross-process lock (`msvcrt`/`fcntl`) and go out in one
  `os.write`; reads skip malformed lines. The two damaged records were rebuilt from `specs/`. *Verify:*
  `test_concurrent_writers_never_tear_lines` (3 processes × 200 lines of 3 KB, every line parses).
- **"Without sponsorship for the next 5 years?"** was matched by the plain "authorized without sponsorship" rule and
  would have been answered Yes. A long-term variant now answers from a value derived from your presets (needs
  sponsorship in future → No), and the airbag checks it. *Verify:* `test_long_term_sponsorship_is_not_the_today_question`.
- **Ashby required fields drawn by CSS.** One board's asterisks were CSS-only, so blank required fields reached submit.
  Required now also means a `required` class, `aria-required`, or `*` in `::after`/`::before`. Follow-up questions that
  appear after an answer are filled on a second pass, and an Ashby "Missing entry" triggers one more pass and resubmit.
  *Verify:* `test_ashby_late_required_question_goes_to_you`.
- **A backspace character inside a rule.** A shell heredoc had turned `\b` into `\x08` in the state rule, so it never
  matched. *Verify:* `test_state_rule_regex_is_clean` (no control characters in runner.py).
- **Dropdowns lost their value under round-robin.** After the field helpers began yielding, another tab could act while
  a dropdown menu was open and close it, leaving work-authorization, sponsorship and EEO selects on "Select...". The
  helpers now yield only before a field; inside a widget they use bounded sleeps. *Verify:* the 10-07 re-run filled
  those selects.
- **Phone country picker.** Options read "United States +1"; the check for a successful pick looked at the wrong
  element and the retry pressed ArrowDown, moving off United States. The check now reads the react-select control and
  the retry uses Enter. Verified on a live Greenhouse form (control shows "+1"), no submission.
- "What company are you currently employed at?" was answered "No" by the previous-employer rule; it now gets your
  current employer. Office-location lists pick a Bay Area office, else remote. Phone country picks "United States +1"
  explicitly (a form failed with "Select a country"). A drafted paragraph is never typed into a dropdown (one run stalled on it).

### Changed (performance; outputs identical)
- `tailor()` 74.3 → 24.3 ms per JD (x3.1), `fit()` 21.8 → 15.1 ms (x1.4) on 155 saved JDs, with identical output on
  all of them (`python scripts/bench_tailor.py <old tailor.py>`). Cached vocabulary and compiled patterns, a substring
  prefilter before each boundary regex, per-fact hit memo, positions instead of `list.index` in sort keys
  (O(k² log k) → O(k log k)), overlap groups as a dict (O(k)).
- `events.read()` is incremental (parses only new bytes), so the per-job rate cap and duplicate check are O(new lines)
  instead of re-reading the whole log; the knowledge graph uses the same reader and no longer scans every edge per
  application (O(A·E) → O(A + E)).

### Changed (CI)
- Branch protection no longer applies to admin pushes: `main` can be fast-forwarded right away (user request). CI
  still runs on every push and pull request, and the local pre-push privacy hook still blocks leaks.

### Removed
- **No scheduled runs.** The Windows task "REGEN public feed" and the daily Claude routine are disabled; the engine runs
  when you start it (user decision 2026-10-07).

## [0.7.1] - 2026-10-07 · "Live, readable, reachable"
### Added
- **Motion on the live view, all from real data:** recent events play as a paced stream (each sentence sends a light to its station), the public site loops the last week of real activity (labelled "replaying"), a twinkling field of one point per ~25 watched boards, light flowing along the pipeline, and the lane tree grows on load with beads that breathe.
- **Accessibility:** beads and graph nodes are keyboard buttons (Tab, Enter/Space, Escape closes panels and returns focus), visible focus rings, skip links to a screen-reader text version of the tree and graph, dialogs with labels, `prefers-reduced-motion` and `prefers-contrast` support.
- **Trace:** every public feed push is a `published` event; the 30-minute publisher logs to `workspace/logs/publish.log`.
### Changed
- `site/` is no longer tracked: the feed is published to `gh-pages`, and Render serves the Next.js app from `main` (https://regen-engine.onrender.com).

## [0.6.4] - 2026-10-06 · "Your inbox is a job board"
### Added
- **Email job alerts as a lead source** (`python -m engine alerts <file>`, `engine/discovery/alerts.py`). LinkedIn, Indeed, Glassdoor, ZipRecruiter and Handshake alert emails list roles but hide the employer's posting behind their own apply flows. Each listing now becomes a lead: domain filter, staffing/aggregator drop, already-applied check, then the newgrad resolver finds the company's own Greenhouse / Ashby / Lever / Workable board and matches the title there. Resolved jobs go to `queue.json` and their boards join the registry; unresolved ones are merged into `workspace/alert_leads.json` (never overwritten).
- **`engine/discovery/gmail_alerts.js`**: run in a signed-in Gmail tab. It reads alert emails through Gmail's own print view (same origin, no API key, nothing leaves the browser) and extracts only title / company / location per listing, with one parser per sender. No links, tracking ids or message bodies are kept.
- `newgrad.resolve(..., source=)` so every resolved job records where it was found.

### Added
- **Live public face.** `apps/web` has a public mode (`NEXT_PUBLIC_REGEN_MODE=public`): a Next.js route (`/api/public`, cached 30 s) proxies the anonymized feed, and the live view and memory graph animate new events as they arrive. Deployed by `render.yaml` as a Node web service on Render; it never sees personal data.
- **Public feed publisher.** `python -m engine site --push` builds the anonymized replay plus an anonymized graph (lanes, roles, ATS, outcome types with opaque ids; no companies, Fact Bank text or answers), runs the leak check, and pushes it to `gh-pages` through a git worktree. The pre-push privacy hook now resolves the main checkout, so worktree pushes are gated too.
- **Current libraries.** Next.js 16.4, React 19.3, TypeScript 5.9 (7.0 waits on openapi-typescript), FastAPI 0.142, uvicorn 0.54, Pydantic 2.13, psycopg 3.3, Postgres 18, Node 24 and Python 3.13 images, MCP SDK 2.x (`MCPServer`).
- **v0.7 platform, first cut** (`apps/`):
  - `apps/api`: FastAPI + Pydantic, read-only (Snapshot, Application, HumanItem, Outcome, Event, Narration). Endpoints: `/api/snapshot`, `/api/applications`, `/api/human`, `/api/outcomes`, `/api/events`, `/api/narration`, `/api/proof/{png}`, `/api/stream` (SSE). Source is Postgres (`REGEN_DATABASE_URL`) or `events.jsonl`.
  - `apps/api/migrate.py`: events.jsonl to an append-only Postgres table (trigger refuses UPDATE/DELETE; sha-deduped, so it's safe to re-run).
  - `apps/web`: Next.js 15 + TypeScript with types generated from the API's OpenAPI. The live view has a pipeline of five stations and a lane tree of proof-backed applications. Clicking a bead opens the proof screenshot, the Fact Bank ids the resume was built from, and every question with the answer given. Narrator plus "waiting on you".
  - `deploy/platform.compose.yml`: db + migrate + api + web, all on 127.0.0.1, workspace mounted read-only.
- Answer rules: 18+, time zone, "how soon can you start", "first learn about X as an employer", AI dev tools (only from the Fact Bank line about daily Cursor/Claude Code use). A test fails if any rule matches an arbitrary label: a trailing `|` once made a pattern match everything, and the test caught it before any form did.
- Public site: company names that are everyday words are checked only in name-shaped forms ("applied - role"), so "Applied to a company" no longer blocks the build.
- **Workable apply adapter** (`fill_workable` / `submit_workable`): resume, name/email/phone, address as city/region/country (the form's own hint), free-text and Yes/No (`role=radio`) questions by `aria-labelledby`; cookie banner declined. Cloudflare Turnstile is detected by its text and goes to the human queue.
- "Will you require work authorization of any kind?" is answered as the sponsorship question (it was matching "authorized to work").
- **Lever apply adapter** (`fill_lever` / `submit_lever`): resume upload, standard fields, custom questions (text, textarea, radio, checkbox, select), location autocomplete restricted to your state/US, EEO selects declined. A visible hCaptcha/reCAPTCHA is never solved: the job goes to the human queue with the form filled. First run: 3 Lever forms filled end to end; one stopped at a real image CAPTCHA.
- Answer rules: country, state/province, F-1 status (preset `f1_status`), "file a petition ... employment-based visa" (sponsorship), current/former employee, referred by, expected annual compensation, current company (preset `current_company`). Yes/No into a free-text box is allowed when *any* sentence of the label is a yes/no question.

### Fixed (seen on real forms)
- "How did you hear about this job? (LinkedIn, Indeed, referral...)" received the LinkedIn URL because the link rule matched first; the how-heard rule now comes first.
- Location autocomplete: "San Jose" alone resolved to San José, Costa Rica. Location questions now answer "City, State", and the Lever box only accepts a suggestion in your state or the US.
- Core-stack gate matched "rust" inside "trust" (zero trust, public trust); stacks now match as whole words.
- A job title naming a non-US city ("Team Lead - Lisbon, Portugal") listed as plain "Remote" is now filtered as non-US.

### Changed (from rejection analysis)
Three rejections in two days were read against their job descriptions. Two jobs required 4+ years against 3 years of experience; one also centered on a stack the candidate doesn't list. The fast turnaround (34-45 h) points to automated knockout screens.
- **Years gate uses your real number.** `fit()` now blocks any JD whose minimum years exceeds `years_experience` from the presets (it allowed up to 4 before).
- **Core-stack gate.** A JD that *requires* a language or stack (strong / proficiency / required / must) that the Fact Bank doesn't list (C#, Rust, Scala, Kotlin, Swift, Ruby, PHP, embedded, HDL) is skipped as `core stack: X`.
- **JD spelling on the resume.** When the JD names a skill you have with a different spelling (Postgres, RESTful, Golang, K8s, large language models...), the skills line shows `PostgreSQL (Postgres)`, so ATS keyword matching hits. `validate()` only accepts a changed skills line when stripping the alias table gives back the original line exactly, so nothing new can be added. Coverage counts these spellings.
- **No duplicate accomplishments.** Fact Bank `_overlaps` groups versions of the same accomplishment; tailoring picks at most one per group. One extra skills line (e.g. Salesforce, AI dev tools) is added when the JD clearly asks for it.

### Fixed
- **Education dates no longer get the availability answer.** Greenhouse education blocks label their fields "Start date month / year" and "End date month / year", and the "when can you start" rule matched them, so a degree's start year was filled with the availability preset. A number input rejected it and the job went to the human queue. These fields now come from the Fact Bank's highest degree (`runner.edu_dates`), checked before the availability rule. With no Fact Bank entry they go to the human queue.

- **Rejections with truncated snippets are now caught.** Inbox snippets often stop mid-sentence ("...high volume of applicants for this role and unfortunately"), so a rejection was logged as "other". New patterns: "move ahead with other", "unfortunately have decided", "weren't selected", "high volume of applicants ... unfortunately". Test: `test_rejection_with_truncated_snippet`.

- **"What city and state do you reside in?"** got only the state (the state rule matched first). A combined city + state rule now comes first. Test: `test_city_and_state_combined`.

### Why
An active job seeker's inbox gets well over 100 matched listings every few days, and they were going unused. First run: 146 listings -> 93 leads -> **30 resolved to the employer's ATS (32%, vs ~10% for newgrad-jobs)**.

### Verify
`python -m pytest -q` (new `test_alert_parse_and_leads`: badge/header rows dropped, staffing filtered, Bay Area normalized). Then `python -m engine alerts workspace/alerts/<date>.txt` prints each resolved job and a summary line, and writes an `alerts` event with the counts.

## [0.6.3] - 2026-10-06 · "Private by construction"
### Security / privacy
- **No personal defaults in code:** every eligibility and status answer (sponsorship, work authorization, clearance, relocation, onsite, degree, enrollment, start date, salary, location in US, relatives, non-compete…) now comes only from the git-ignored `profile/presets.json`. An unset preset or an unfilled `<placeholder>` goes to the human queue. A test forbids hardcoded Yes/No answers.
- **Public site:** skip reasons are published only as generic categories (eligibility requirements, seniority, graduation window), so nothing about anyone's citizenship or visa status can be inferred.
- **Privacy gate** (`scripts/privacy_scan.py`, `.github/workflows/ci.yml`): every PR and push to `main` must pass:
  - PII patterns, forbidden paths, noreply-only commit emails
  - keyed HMAC fingerprints of private terms (`.privacy/denylist.json` + the `PRIVACY_KEY` secret)
  - a public-site wording check

  Local mode adds a full git-history scan and a pre-push hook. `main` branch protection requires the gate and tests for everyone, admins included.
- **Scrubbed:** real company names in tests (now fictional: Acme, Globex, Initech, Hooli, Umbrella, Vandelay), docs and comments; personal wording in comments and the changelog.
- **Tests** use a fictional persona (`tests/fixtures/presets.json`, Jane Doe) via `REGEN_PRESETS`.
- Merges now use a noreply author identity; earlier server-side merge commits exposed a personal email in commit metadata, which was removed by resetting the public history.

### Added
- README rewrite (hero screenshot of the anonymized demo, badges, why-star, live demo, star history), `SECURITY.md`, `CONTRIBUTING.md`, PR template with a privacy checklist.
- Roadmap v0.7 **Platform:** Next.js + TypeScript live view, FastAPI + Pydantic API, Postgres.

## [0.6.2] - 2026-10-05 · "A tidy tree"
### Changed
- The live view's applications are now a **tree**, not floating dots. Stations sit on a straight, evenly spaced line (the pipeline is the trunk). From *applying*, a trunk rises and splits into one tidy stem per **resume lane** (full-stack, AI, data, backend, platform, earlier). Each bead on a stem is one application sent with proof, and each lane's name and count sit on top of its stem. A caption explains it and always fits on screen; hovering a bead names the application (the role only, on the public site).
- The snapshot carries each verified application's lane (from the `resume` event that built it).
- README: a "Deploy to Render" button replaces a public URL that wasn't live yet.

## [0.6.1] - 2026-10-05 · "A public face, a lighter engine"
### Added
- **Public site** (`python -m engine site` -> `site/`, deployed on Render via `render.yaml`, free static tier): the live view in demo mode, replaying the last 7 days of real activity **anonymized**. Role titles, stages, outcomes and skip reasons are kept. Company names, anything waiting on the candidate, answers, URLs, emails and files are removed. A one-line intro and a repo link are added for visitors. Identical lines collapse ("16 companies confirmed…").
- **Leak airbag:** the export refuses to write if any company name from the event log would appear on the public page.
- Embers are captioned ("each light: an application sent, with proof"); hovering one names the application in the local view and the role only in the public view.

### Changed
- **Lighter discovery:** boards are streamed through the filter as they arrive (`fetch_all(keep=..., keys=...)`), so a pass holds only fresh postings plus id strings instead of all ~110k posting objects. Measured peak Python memory for a full pass: 317 MB -> 260 MB; the remaining peak comes from parsing large boards concurrently. Worker pool 32 -> 24.
- Corrections supersede: the public replay shows only the latest, corrected record for a job. Two skips logged as "15+ yrs" by the old years parser were corrected to "5+ yrs" with appended `correction` events.

## [0.6.0] - 2026-10-05 · "The live engine"
### Added
- **Live view** (`engine/live/`, `python -m engine live`): one calm screen, not a dashboard. Work travels as light through five stations (listening, judging, writing, applying, hearing back). The engine narrates each real event in one plain sentence. Every verified application (confirmation screenshot on disk) becomes a permanent ember, and the verified count is the only number shown. "N things are waiting on you" lists what needs you **now**, from each job's latest status.
- Server: standard library only, read-only, bound to 127.0.0.1, Server-Sent Events, strict CSP. Page: one HTML file, Canvas 2D, no build step, no CDN, no tracking. Respects `prefers-reduced-motion` and light/dark.
- Docker `live` service in `deploy/watcher.compose.yml`: read-only workspace mount, published on 127.0.0.1 only, 128 MB.
- `docs/FRONTEND.md`: concept, anti-dashboard rules, frontend roadmap (60-second day replay, click-an-ember proof, lane "workers", phone access, anonymized public demo) and free-service research (Tailscale, Cloudflare Tunnel, self-hosted ntfy, GitHub Pages, Artifacts, InsForge, three.js/Rive).
- Narration is evidence-based: it never says "proof saved" unless the file exists, and never shows invented counts. *Verify:* `python -m pytest -q` (`test_live_narration_is_plain_and_evidence_based`).

## [0.5.1] - 2026-10-05
### Fixed
- Docker watcher was restarting at the 256 MB memory limit (a full poll holds about 110k postings). Limit raised to 1 GB; verified with a full poll (about 750 MB, 0 restarts). *Next:* stream boards through the filter instead of holding all postings, to bring this down.

## [0.4.0] - 2026-10-05 · "More sources, fewer stalls"

### Added
- **Multi-ATS discovery** (`engine/discovery/ats.py`, `scan.py`): one scanner for **Greenhouse, Ashby, Lever and Workable** public board APIs, normalized to a single job record (`ats, token, id, company, title, location, posted, url`). About 2,300 boards (110k postings) scan in about 45 s, up from 345 Greenhouse boards.
  *Verify:* `python -m engine scan 1` prints `scanned N boards, M postings`.
- **Board registry** `workspace/boards.json`, migrated automatically from the old `boards.txt`. `python -m engine boards harvest` grows it from the SimplifyJobs JSON lists and the READMEs of speedyapply, vanshb03, SimplifyJobs and ReaVNaiL. Boards that 404 are recorded under `dead`.
- **`watch` mode** (`engine/discovery/watch.py`): polls every board on an interval (default 10 min) and announces only postings that didn't exist on the previous poll, with minutes-since-publish. Writes `workspace/new.jsonl`, logs `discovered` events, and POSTs to `REGEN_WEBHOOK` (Slack, Discord, n8n, Zapier) if it's set. The first poll only seeds `seen.json`, so it never floods.
- **newgrad-jobs.com source** (`engine/discovery/newgrad.py`, `airtable.py`): reads the site's public Airtable views (SWE, AI/ML, Data Eng; about 150 new rows a day). Its links hide the employer's posting behind jobright.ai, so each row is resolved to the company's **own** Greenhouse/Ashby/Lever board by company slug and title match. Resolved boards join the registry, so later scans watch them directly. Unresolved rows go to `workspace/leads.json`.
- **JD fit gate** (`engine/tailoring/tailor.py: fit`): before a resume is built, the job description is checked for citizenship/ITAR, clearance/polygraph, "no sponsorship", grad windows you're outside of, and years required above your level. Blocked jobs are logged as `SKIPPED` with the reason and never re-queued. `--force` overrides.
- **Per-job tailoring, still Fact-Bank-only** (`tailor.tailor`): keeps the lane's shape (same roles, bullet counts and project count) but picks and orders bullets, projects and skill lines by how many of the job's technologies they mention. Candidates are only the bank's own facts for that role, and `validate()` still gates the result. Each build prints a coverage line ("resume covers 15/15 JD terms").
- **Transparency log:** every `resume` event records the exact fact ids, projects, skills and lane used, so every claim on every resume traces to a Fact Bank entry.
- **`inspect` command** (`engine/apply/inspect_form.py`): headless read of any Greenhouse or Ashby form. Lists each field, whether it's required, its options, and the answer the engine would give, or `UNKNOWN`. Use it to see which questions a job needs before applying.
- **Answer bank** `profile/answers.json` (optional): answers you approve once and that are reused on every form (`[{pattern, answer, source}]`). Checked after per-job `extra`, before the built-in rules.
- **Data lane** support: routing rule for data-engineering titles (lane lives in your private `profile/lanes.json`).
- **Tests** (`tests/`, `python -m pytest -q`): filters, harvesting, fit gate, Fact-Bank validation of tailored specs, answer rules and option matching. They run against `profile.example/` and a temp workspace, never your real data.

### Changed
- `batch` is ATS-agnostic (Greenhouse, Ashby, Lever, Workable job descriptions) and records `ats` and `lane` per job.
- Domain filter moved to `engine/discovery/filters.py` and is shared by every source. It adds a real US-location test (state codes, US cities, non-US country list), excluded employers (configurable, e.g. ITAR-restricted), and more excluded levels and titles (VP, architect, polygraph, mobile, 2027, research scientist...).
- `engine/discovery/greenhouse.py` is now a compatibility shim over the new modules (old imports keep working).
- `profile.example/domains.json` now mirrors the engine defaults. The old example silently weakened the filter.
- Greenhouse selects open once and choose from the full option list, and only fall back to typed search for long or async lists. EEO-heavy forms went from minutes per question to seconds.
- Ashby comboboxes (e.g. location autocomplete) choose the best matching option instead of requiring exact text.

### Fixed
- **Runner stalls:** every Playwright action now times out (15 s, 45 s for navigation) instead of hanging a whole batch. Each field is logged as it's filled.
- **Double-apply guard:** `apply` skips any job whose URL is already `SUBMITTED` in the event log, so re-running a batch is safe.
- **Wrong answer:** the disability question ("...limits one or more of your *major* life activities") was answered "Computer Science" by the field-of-study rule. EEO and demographic questions are now matched first, and `major` is word-bounded.
- **Wrong answer risk:** a Greenhouse select with no matching option used to click the first of up to 3 filtered options. Now only a single remaining option that contains the searched text is accepted. Otherwise the job goes to the human queue.
- **ACK matching:** "I have read and agree", "I understand", "Acknowledged"... are recognized, and negatives ("I do not agree", "Not now") are never picked.
- **Over-broad rules:** "source" no longer catches "Open source community"; "race" no longer catches "tracing"; "community" no longer catches unrelated questions.
- New provable answers: "based in the U.S.", "earliest start", "preferred location", "do you have a college degree", "currently enrolled", "highest level of education". `type=url` inputs (Ashby LinkedIn) are filled.
- Years-of-experience parser: "5 to 15+ years" means 5+ (it used to read 15+), and en-dash ranges ("4–7 years") parse correctly.
- Grad-window check no longer blocks "degree **by** June 2027", which a 2026 graduate already meets.

- **Wrong answer risk:** "Are you authorized to work in the US *without* sponsorship?" used to fall into the generic "sponsorship -> Yes" rule. It now has its own preset, `authorized_without_sponsorship`; when that's unset the job goes to the human queue.
- **Wrong answer risk:** free-text boxes never get a bare "Yes"/"No" unless the label is a yes/no question (an optional "What address will you work from? If you'd relocate…" box would have received "Yes"). Work-address questions now get your city and state.
- Dropdown matching ignores curly quotes and dashes (`Master’s` = `Master's`) and tries same-fact aliases (`California` -> `CA`, `Master's` -> `Master of Science`).
- More provable answers: "Legal Full Name", "based in or around the Bay Area" (derived from your preset city), "relatives that currently work at…", data-use consent ("Do you authorize X to use your information"). Street address is filled only if you add `address_line1` to presets.
- **newgrad resolver:** a board is cached only after a lead title actually matched there. A same-slug board from a different company (e.g. `ashby:pylon`) is no longer trusted, and misses are retried after 7 days instead of never.

- **False SUBMITTED (critical):** Greenhouse success detection matched the bare word "confirmation" anywhere on the page, so a form waiting at the email-code step was once logged as submitted. Now the code step is checked first, and success needs explicit thank-you/received wording or a `/confirmation` URL, plus the submit button gone. The one affected record was corrected with an appended `correction` event (the log stays append-only), and every other submission was re-verified against its proof.
- Dedupe (`apply` guard and discovery) uses each job's **latest** status, so a correction overrides an earlier event.
- Greenhouse **education block** (Degree / Discipline / School react-selects inside `.education--form`) is now scanned and filled. School names match Greenhouse's spelling variants ("…University-Fullerton").
- ACK recognizes "I will read…"; the select fast path opens menus that a click only focused.
- **Ashby bot check:** "flagged as possible spam" is reported as `BOT-CHECK` (apply manually with the prepared resume) and never worked around.

### Safety airbags + SOS + outcome loop
- **Airbags** (`engine/safety.py`): before any submit, the job is stopped, flagged (`workspace/flags.jsonl` + a `flag` event) and skipped if:
  - the form asks for sensitive data (SSN, bank/card, password, date of birth, license/passport numbers)
  - a field asks for payment or fees
  - the form is on an unexpected site
  - a legal answer (sponsorship / work authorization) disagrees with your presets
  - the daily cap (`REGEN_MAX_PER_DAY`, default 25) or 3 per company per day is reached

  **Kill switch:** create `workspace/STOP` and the runner halts before the next job.
- **SOS email** (`engine/notify.py`): stdlib SMTP from your own mailbox using an app password in `.env`; no third-party service. Without it, alerts go to `workspace/sos_outbox.md`. `python -m engine sos-test`.
- **Outcome loop** (`engine/feedback/inbox.py`): `inbox <msgs.json>` (operator-fetched) or `inbox --imap` (read-only IMAP) classifies recruiting email as confirmation, OA, interview, rejection, offer, action or **scam**, and links it to the exact application by company and role title. Each becomes an `outcome` event plus a line in `workspace/outcomes.md`. Interviews, OAs, offers and scams trigger an alert. Conditional wording ("if there's a fit we'll schedule an interview") is not mistaken for an invite.
- `learn`: reply / OA / interview / rejection counts by resume lane and ATS -> `workspace/learnings.md` (the signal for adapting lanes and sources).
- JD fit gate: `ITAR` is word-bounded (it had matched "mil-**itar**-y" and skipped an eligible job).
- "Are you currently, or have you previously, worked at X?" uses your `previous_employer_of_company` preset. Questions about working *with a partner/supplier* still go to you.

### Always-on + honest numbers
- **Docker watcher** (`Dockerfile`, `deploy/watcher.compose.yml`): `watch 10 --newgrad` runs in a small container with no browser, as an unprivileged user, on a read-only root filesystem, with all capabilities dropped, a 256 MB / 0.5 CPU limit, and `restart: unless-stopped`. `profile/` is mounted read-only and `workspace/` holds all state. *Verify:* `docker compose -f deploy/watcher.compose.yml logs -f`.
- `watch --newgrad` also pulls newgrad-jobs.com leads about once an hour (cached, so cheap).
- **`report` command:** counts only *verified* submissions, meaning each job's latest status is SUBMITTED and its confirmation screenshot exists on disk. No inflated totals.
- **Ashby cooldown:** after Ashby flags an automated submit, Ashby auto-submits pause for 24 h. Forms are still filled and screenshotted, and you click submit. This protects your standing with Ashby-hosted employers.

### Transparency
- Every `application` event now stores the full question -> answer list the filler used, so any submission can be audited after the fact.

### Policy (unchanged, now enforced in code)
- **Arbitration** agreements are never answered by default. They need a per-job `extra` (your approval for that company).
- Jobs on ATSs without an adapter (Lever, Workable) get a tailored resume and a `NEEDS YOU` entry. They're never pushed through the wrong filler.

## [0.3.0] - 2026-10-05
- Engine package, CLI (`scan / feed / batch / tailor / apply / status`), Greenhouse + Ashby apply, Fact Bank validator, event log, memory stack definition, architecture docs. First real run: 7 applications.
