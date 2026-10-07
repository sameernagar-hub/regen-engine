# Changelog

Every change to the engine, newest first. Each entry says **what** changed, **why**, and **how to verify** it,
so a reviewer can check the work without reading the whole diff.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow the README roadmap.

## [0.6.4] - 2026-10-06 · "Your inbox is a job board"
### Added
- **Email job alerts as a lead source** (`python -m engine alerts <file>`, `engine/discovery/alerts.py`). LinkedIn, Indeed, Glassdoor, ZipRecruiter and Handshake alert emails list roles but hide the employer's posting behind their own apply flows. Each listing now becomes a lead: domain filter, staffing/aggregator drop, already-applied check, then the newgrad resolver finds the company's own Greenhouse / Ashby / Lever / Workable board and matches the title there. Resolved jobs go to `queue.json` and their boards join the registry; unresolved ones are merged into `workspace/alert_leads.json` (never overwritten).
- **`engine/discovery/gmail_alerts.js`**: run in a signed-in Gmail tab. It reads alert emails through Gmail's own print view (same origin, no API key, nothing leaves the browser) and extracts only title / company / location per listing, with one parser per sender. No links, tracking ids or message bodies are kept.
- `newgrad.resolve(..., source=)` so every resolved job records where it was found.

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
