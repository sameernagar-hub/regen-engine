# Handoff: 10-30 ~23:45. Stack is DOWN (gear N, drained, compose stop, volumes kept). main = 4a05818 pushed.

## Done 10-30
- `engine vc`: venture portals (YC pages + yc-oss hiring list, Getro/Consider fund boards, Next.js server-action
  portals from profile/vc_portals.json) -> leads -> employer ATS; careers-page crawl for unresolved startups.
  In the pipeline sources step (hourly self-throttle). YC Work-at-a-Startup-only roles: workspace/yc_waas.md (user).
- Cover note per batch job (compose.cover_note) fills optional cover letters / "why" boxes from Fact Bank facts.

## Next
- On start: shift to gear 2. The desk lost its two filled YC tabs on recreate: re-request Axiom + Drillbit
  (workday.request from batches/yc_test.json and manual/yc_dry.json). YC jobs reach the desk 2 a pass; the user
  ticks hCaptcha + Submit at http://127.0.0.1:6080.
- Watch whether notes change outcomes (feedback.md); consider more fund portals in profile/vc_portals.json.
- yc probe: ~1.3k YC companies left, 120 per run.

# Handoff: 10-19 ~23:00. Stack is DOWN (stopped cleanly, 0 claimed, volumes kept). main = fc2a489, everything merged.

## START (if down)
`cd regen-engine && REGEN_MCP_WRITE=1 REGEN_DAYS=30 REGEN_MAX_PER_DAY=150 REGEN_TABS=4 REGEN_ASHBY_PER_PASS=1 REGEN_LOOP_MIN=3 REGEN_SOURCES_EVERY=3 REGEN_MAX=150 docker compose -f deploy/bank.compose.yml up -d --scale applier=1`
Speed is now the gearbox: http://127.0.0.1:3000/gearbox or `docker exec -u 10001 deploy-pipeline-1 python -m engine gear 3`.
After a new compose service, recreate the supervisor FIRST: an old supervisor stops undeclared services (it killed
`feedback` once with exit 137).

## Done 10-19
- `feedback` container: IMAP every 30 min -> outcomes -> rejected vs other JDs -> `workspace/feedback.md` +
  `workspace/learned_gate.json`. Phrases block only when significant after a Bonferroni correction; first pass read 48
  new outcomes, 42 rejected JDs, 0 blocking (15 boilerplate phrases stay proposed). Three OA mails (one employer's
  assessment request) raised SOS, saved to sos_outbox.md (SMTP not configured in the container).
- Gearbox: gears N/1-4 set the applier range + scan interval; clutch couples learned phrases to the fit gate.
  Web `/gearbox` (animated constant-mesh box, shifter, clutch, rules table) + gearbox part on the home engine.
- Mis-submit found in today's report: an automotive "trim design release" role passed via "release engineer"
  titles -> automotive design words are non-software titles now (test added).

- MCP at every level: 43 tools; discovery tools add boards / feeds / leads straight to the discover stage. Bank MCP
  writes ON (`REGEN_MCP_WRITE=1` in the start command). Claude Code: both servers registered at local scope on the
  workspace root (regen-engine folder itself is not trusted yet; its .mcp.json stays pending until you trust it).

## Next
- Ashby cooldown (bot flag 10-19 22:05) ends ~10-20 22:05: Ashby jobs wait until then.
0. Use the discovery MCP each session: `discovery_sources`, then `feed_add` / `companies_probe` / `leads_add`.
1. Let reposync open the PR for this commit; fast-forward main after CI (user OK).
2. The public proxy dataset has no /api/control/gearbox: the page falls back to built-in demo numbers; add it to
   scripts/proxy_dataset.py when the site is next rebuilt.
3. Older items below still apply (Workday desk Apply button, state dropdown, public feed airbag word).

# Handoff: 10-18 ~22:00. v1.0.0 RELEASED. Stack is DOWN (stopped cleanly, volumes kept).

## START
`cd regen-engine && REGEN_DAYS=30 REGEN_MAX_PER_DAY=150 REGEN_TABS=4 REGEN_ASHBY_PER_PASS=1 REGEN_LOOP_MIN=3 REGEN_SOURCES_EVERY=3 REGEN_MAX=150 docker compose -f deploy/bank.compose.yml up -d --scale applier=1`
Health: `docker exec deploy-supervisor-1 python -m engine fleet`; control room http://127.0.0.1:3000/control now shows
each stage live (from heartbeats). Draft override ON (re-armed 21:29 so parked jobs retried on the fixed filler).
Ashby cooldown ended ~22:39 10-18: 1/pass. Gate every commit: `git add -A`, then `python scripts/privacy_scan.py`
and CHECK ITS EXIT CODE (piping it into `tail` hid a leak once; caught before push). Company names never in the repo.
Push main by fast-forward with a POSIX-path python shim on PATH (a `C:/...` PATH entry breaks on the colon).

## Done 10-18 evening
- **v1.0.0 published** (tag at ba1b229, main fast-forwarded, PR #18 merged by the push, Render 200).
- Local commits after the release (reposync pushes them to a new PR on start): dedupe of "<X> Careers page" vs "<X>"
  (two roles were each submitted twice today), employer/title "(or most recent)" rules, sponsorship sentence
  options + a negation bug ("do not require" read as "require"), Accept ticks acknowledge boxes, fit gate
  "does not offer support or sponsorship" / "should not apply if you require sponsorship".
- Live everywhere: per-stage pipeline beats, control room stage details, applier cards include /needs retries,
  supervisor `liveness()` watchdog restarts silent containers, fleet shows one row per singleton service, scans
  record `discovered` (Discover station read 0 since the Docker loop).
- Filler: graduate-degree buckets, open-ended salary buckets, "willing to relocate" sentences, "If yes" follow-ups
  blank, title-only citizenship/clearance gate.
- Applications today: see `engine report`; 6 by 20:45, more after the 21:29 retry (monitor logged more submits).

## Next (in order)
1. Start the stack; let reposync open the PR for the post-release commits; fast-forward main after CI (user OK).
2. Supply is the limit: "select 0 of 748" at 21:00 = Workday (~330, sign-ins) + Ashby (cooldown) + parked.
   After the cooldown, Ashby gives ~1 per 3-min pass.
3. Workday desk: after sign-in the filler stopped on the job page ("no Next or Submit button on step 1"): it must
   click Apply / "Apply Manually" first. Fix in engine/apply/workday.py, test on a tenant that sponsors.
4. Public feed airbag blocked one push (a word that is both a company and a database name). Decide mask vs allow-list.
5. A Greenhouse "state/region" dropdown didn't take "California" (option text unknown; read the proof).

## Needs the user
- Workday: create tenant accounts yourself (Claude cannot create accounts or type passwords), sign in in the desk,
  then "Fill it in the desk". Seven Workday postings (one automaker tenant + one more) say no sponsorship: skipped, don't sign in for them.
- Lever CAPTCHA forms (filled, finish by hand): e.g. the Charlotte associate programmer role.

# Handoff: 10-18 ~01:00. Stack is DOWN (stopped cleanly, 0 claimed, volumes kept). Goal next: RELEASE v1.0.0, then use it.

## START
`cd regen-engine && REGEN_DAYS=30 REGEN_MAX_PER_DAY=150 REGEN_TABS=4 REGEN_ASHBY_PER_PASS=1 REGEN_LOOP_MIN=3 REGEN_SOURCES_EVERY=3 REGEN_MAX=150 docker compose -f deploy/bank.compose.yml up -d --scale applier=1`
Health: `docker exec deploy-supervisor-1 python -m engine fleet`. The draft override is ON (`engine draft status`).
Ashby cooldown ends ~10-18 22:39; keep 1/pass after. Gate every commit: `git add -A` FIRST, then `python scripts/privacy_scan.py`.

## Release checklist (do first, in order)
1. Start the stack so reposync pushes the 2 local commits (dbe457e, 87e400c) + this handoff to PR #18 (bot/sync).
2. Wait for PR #18 CI (privacy gate + tests) on the new head. Locally: `py -3.14 -m pytest -q` (215 expected) and
   `py -3.14 scripts/privacy_scan.py --history`.
3. Re-check for release: README numbers (tests, boards, submitted), CHANGELOG [1.0.0] covers everything since 0.16.3
   (incl. override, background presets, mechanical blocker, harvest feeds, gone postings, IMAP NOOP), SECURITY.md port
   table, profile.example/presets.json has every preset key the runner reads, `engine --help` lists `draft`.
4. Merge by FAST-FORWARD only (never GitHub's merge button: it stamps the personal email): `git push origin main`
   once the branch CI is green; user approves this step.
5. Publish the draft release v1.0.0 (already created, target main): update its notes with the override + 10-18 items,
   then `gh release edit v1.0.0 --draft=false` (user approves).
6. Render auto-deploys main; check https://regen-engine.onrender.com loads. Then stop feature work: use the engine.

## Done 10-17 / 10-18
- v1.0.0 review fixes (see CHANGELOG [1.0.0]): Host checks, desk VNC password, relay origin, live view, memory-stack
  ports, supervisor never retires the last applier, captchas never retried blind, Ashby never resubmitted.
- Human draft override (`engine draft on|off|status`): user's standing approval; agreements accepted, export /
  US-person from presets, open text drafted. Never: unknown facts, human checks, EEO beyond decline.
- Background presets (user 10-18, "never ask these"): criminal_record No, active_immigration_case No,
  covid_vaccinated Yes, adverse_credit No, government No.
- Supply: 30-day window, +~250 boards (HN 12 months + 7 lists), build/release + ML lead titles, closed postings pruned,
  mechanical / manufacturing roles blocked in the fit gate.
- 22 submitted this session (201 total).

## Needs the user
- Workday sign-ins in the desk (/reach, ~320 jobs). Human checks + Lever captcha forms (filled, finish by hand).
- Deemed-export questions: override answers "affects me: Yes" from citizenship; self-certification lists still parked.

# Handoff: 10-17 night (v1.0.0 release review). Stack is UP.

## START
`cd regen-engine && REGEN_DAYS=30 REGEN_MAX_PER_DAY=150 REGEN_TABS=4 REGEN_ASHBY_PER_PASS=1 REGEN_LOOP_MIN=3 REGEN_SOURCES_EVERY=3 REGEN_MAX=150 docker compose -f deploy/bank.compose.yml up -d --scale applier=1`
Don't recreate appliers by hand while the supervisor runs unless they are idle (claimed 0): it races the drain handshake.

## Done 10-17
- v1.0.0 review: API/relay/live-view Host checks, desk VNC password per start, memory-stack ports on 127.0.0.1,
  supervisor never retires the last applier, captchas never retried blind, answer-rule fixes (see CHANGELOG 1.0.0).
- PR #18 (reposync) carries the commits; draft GitHub release v1.0.0 exists (publish after main has the commits).
- 5 submitted today, all 5 confirmed by email (company names stay out of the repo).
- Ashby cooldown started 10-17 22:39 (a captcha was resubmitted; fixed). Ends ~10-18 22:39. Keep 1/pass.

## Supply (why throughput is low)
Of ~730 queued: 317 Workday (need your sign-ins in the desk, /reach), ~270 Ashby (1/pass, cooling now), 77 parked
on your answers (/needs), 50 JazzHR/SmartRecruiters (desk). Discovery window widened to 30 days, sources every 3 passes.

# Handoff: 10-15 late night (~23:15). Stack is DOWN (stopped cleanly; volumes kept). main = this commit.

## START
`cd regen-engine && REGEN_DAYS=7 REGEN_MAX_PER_DAY=150 REGEN_TABS=4 REGEN_ASHBY_PER_PASS=1 REGEN_LOOP_MIN=3 REGEN_SOURCES_EVERY=10 docker compose -f deploy/bank.compose.yml up -d --scale applier=1`
then `docker exec deploy-supervisor-1 python -m engine fleet`; inbox: `docker exec -u 10001 -e HOME=/home/regen deploy-supervisor-1 python -m engine inbox --imap 2`.
UI: http://127.0.0.1:3000/needs (answers), /reach (Workday sign-ins), /control. If `curl 127.0.0.1:8787/api/health` fails, check
`docker ps` shows `127.0.0.1:8787->8787/tcp` for deploy-api-1; if not: `docker compose -f deploy/bank.compose.yml up -d --no-deps --force-recreate api`.

## Done 10-15
- Stale image fixed (Rippling/JazzHR code was not in the running image). Harvest: +161 Rippling, +187 JazzHR boards.
- **Rippling promoted to auto-apply** (ats.FILLED + APPLY_SUPPORTED) after dry runs on 2 real postings filled every field.
  Submit check no longer reads a wrapper `[class*=error]` (the page heading) as an error while the form is submitting:
  2 Rippling applications were logged FAILED mid-submit; confirm from the inbox before any resubmit.
- **Throughput**: discovery window was fixed at 1 day -> `REGEN_DAYS` (now 7). One pass went from 0-1 selected to 20
  selected / 14 dispatched; supervisor scaled to 5 appliers. Pipeline scan list now includes rippling + jazzhr.
- **/needs answers**: your own legal / sponsorship answers were refused (422). Now accepted and kept on THAT job only
  (`answers/job_extra.json` -> the retry batch's `extra`), never in answers.json; EEO / demographic stays decline-only.
  "Apply now" (`/api/control/retry`) 403 in the bank -> returns "already queued" (the answers container retries).
  Answered jobs whose old batch file was cleaned are rebuilt from the ledger (url + resume), so they retry too.
- Tried an automatic "re-check parked jobs" pass: its dry run produced wrong answers (arbitration "No", degree year
  "Master's"), so it was NOT shipped. Parked jobs stay on /needs.

## Do first (in order)
1. **New job-board drivers (user request 10-15): Glassdoor, Indeed, Monster, ZipRecruiter.** Discovery first: pull
   their postings, resolve each to the employer's own ATS link where one exists (then the normal filler applies), else
   list on the reach page with a tailored resume. Their own "easy apply" flows need the user's signed-in account and
   have bot checks: per PLAN.md guardrails these run in ASSIST mode in the desk (user signed in, engine fills, user
   solves any check and clicks submit); never automate captchas or log in with the user's password.
2. Rippling jobs still did not reach queue.json after a 7-day pass (scan date filter / first-seen dates / --hot):
   find why. Some Ashby forms (one employer, 10 jobs): "Missing entry for required field: Location" - fix the places box.
3. Supervisor replaced the api container without its port/network once (probe "Name or service not known" loop):
   make the probe restart via compose config, not a bare container.
4. Ashby 1/pass (215 selectable Ashby jobs wait); raise to 2 only after a clean day.

## Needs the user
- /needs: re-enter answers that were refused before the fix (arbitration, authorization, sponsorship questions).
- Workday sign-ins on /reach (273 Workday jobs). Deemed-export Yes/No for the storage employer still pending.

# Handoff: 10-15 ~00:45 (after v0.14). Stack is DOWN (stopped cleanly, 0 claimed; volumes kept). main = this commit.

## START
`cd regen-engine && REGEN_MAX_PER_DAY=150 REGEN_TABS=4 REGEN_ASHBY_PER_PASS=1 REGEN_LOOP_MIN=3 REGEN_SOURCES_EVERY=10 docker compose -f deploy/bank.compose.yml up -d --scale applier=1`
then `docker exec deploy-supervisor-1 python -m engine fleet`; inbox: `docker exec -u 10001 -e HOME=/home/regen deploy-supervisor-1 python -m engine inbox --imap 2`.
Pushing: this machine has no host Python, so the pre-push privacy hook needs the docker `python` shim (see 10-15 session) or a host Python.

## Do first (in order)
1. **Rippling filler (engine/apply/runner.py fill_rippling)**: dry run on a real US posting filled every field except
   (a) required checkbox groups ("Which coding languages...": use skill_options from the Fact Bank, flag required
   ones as missing), (b) "experience with GitHub and Git?" answered No (Git is not in the Fact Bank vocabulary:
   ask the user / add Git to the Fact Bank, don't guess), (c) submit_rippling must check the Apply button is enabled.
   Then move "rippling" from REACH to OPEN_ATS + APPLY_SUPPORTED in engine/discovery/ats.py (161 boards, no account,
   no captcha seen). Until then Rippling jobs land on the reach list.
2. Harvest the new boards: `docker exec deploy-pipeline-1 python -m engine boards harvest` (rippling + jazzhr
   adapters are new; JazzHR has a required reCAPTCHA -> desk only, like SmartRecruiters).
3. Ashby cooldown ends ~22:40 10-15; pipeline now runs REGEN_ASHBY_PER_PASS=1.
4. User: sign in to Workday employers via /reach "Workday sign-ins" -> watch the first real desk fill.

## Done since the 10-14 handoff
- Desk: Workday sign-in list + Open in desk; SmartRecruiters fill in the desk (bot check is the user's); internal /
  contractor Workday sites hidden. Public feed airbag false alarm fixed (values only; names in titles masked).
- Answers: residence time zone, held US/Canadian citizenship, sex = EEO decline. Age-18 fix + resume check live.
- Discovery adapters: rippling (JSON, first-seen dates), jazzhr (HTML, real dates). Source research: Oracle Cloud
  132 boards (account, like Workday), JazzHR 187, Rippling 161; Recruitee/Breezy too small to matter.

# Handoff: 10-14 night session (v0.14 guardrails, evals, desk), written ~23:45 10-14. Stack is UP.

## START HERE
1. Stack running? `docker ps --format '{{.Names}} {{.Status}}' | grep deploy` -> 12 containers incl. `desk`. If not:
   `cd regen-engine && REGEN_MAX_PER_DAY=150 REGEN_TABS=4 REGEN_ASHBY_PER_PASS=2 REGEN_LOOP_MIN=3 REGEN_SOURCES_EVERY=10 docker compose -f deploy/bank.compose.yml up -d --scale applier=1`
2. Health: `docker exec deploy-supervisor-1 python -m engine fleet` (desk role should say `ready`). Pages: /control,
   /reach (Fill it in the desk), **/evals** (new), desk = http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale.
3. Inbox at start: `docker exec -u 10001 -e HOME=/home/regen deploy-supervisor-1 python -m engine inbox --imap 2`.
4. Same git rule: commit locally (noreply email), reposync opens the PR. Local commits this session:
   a783e43 guardrails, 87df584 evals + desk + age fix + resume check, 6e13353 desk on real Workday + pages, + handoff.

## Done 10-14
- Supervisor guardrails: bounded creates (allowlist applier/eval, HARD_MAX 12, cpu/mem/pids caps, no privileged /
  CapAdd / Docker socket), enforce() every minute (stop undeclared, live-bound unlimited appliers, 12 h TTL for
  supervisor-made appliers). Live: all appliers bounded, ~225 pids used while applying.
- Eval containers: B8 supervisor (7/7), B9 API p95 (~340-580 ms), B10 bus (~1.2-1.7 s). Triggers: reposync commit,
  6 h schedule, `supervise --eval`. Verified live: manual + commit evals ran, rc 0, reaped, history at /evals.
- **Bug fixed: "Are you at least 18 years of age/old?" was answered No** (years-of-experience rule). 11 forms, 3
  SUBMITTED with "No": one health-tech SWE I (10-11, since rejected) and two roles at one crypto exchange (10-13).
  User confirmed (10-14) they are 26. Fix deployed + regression test.
- Resume-attached check before every submit on every ATS (was Greenhouse only): `RESUME UPLOAD FAILED`, not submitted.
- Workday desk + filler: verified on a real tenant up to the sign-in step (stops: "sign in to <tenant> in the desk").
  Past sign-in the wizard steps are only verified on the local look-alike: **first real fill needs watching**.
- Supply sweep: boards 5,094 -> ~5,105, +22 queue jobs (queue 531), reach list 179 (workday 172).

## Next (in order)
1. **User signs in to Workday employers**: /reach -> "Workday sign-ins" -> "Open in desk" (list sorted by job count). SmartRecruiters jobs
   fill in the desk too (bot check is the user's to solve; never automated). Then press "Fill it in the desk" on /reach; watch the first one
   and fix selectors for My Information / My Experience / Application Questions / Voluntary Disclosures from what the
   real DOM shows (proof screenshot + `application` event detail). 172 Workday jobs are waiting on this.
2. SmartRecruiters: done in the desk (stops before Submit). Next: verify the real Easy apply form once the user solves a check.
3. New open-ATS adapters (public job JSON + account-free apply form): Recruitee (`{co}.recruitee.com/api/offers`),
   Breezy (`{co}.breezy.hr/json`), Pinpoint (`{co}.pinpointhq.com/postings.json`), BambooHR (`{co}.bamboohr.com/careers/list`),
   Rippling ATS, Teamtailor. Discovery first (reach rows), filler per ATS once a look-alike test exists.
4. Ashby queue (271) is the bottleneck at 2/pass; no new cooldown seen today. Consider 3/pass only after a clean day.
5. Wiki pages still open: Ledger, Data bus, Repo sync, Answer queue, MCP, Supervisor (guardrails), Evals, Desk.

## Needs the user
- Tell the crypto exchange (2 roles) the 18+ answer was a form-filler error, if you want: the submitted answer was "No".
- Sign in to Workday tenants in the desk (your accounts; the engine never types passwords).
- The storage-hardware employer deemed-export Yes/No still pending; GitHub "Keep my email private" still off; 3 Gmail drafts to delete.

# Handoff: 10-13 session (v0.13 "Reach"), written ~00:15 10-14. Stack is DOWN (volumes kept).

## START HERE (engine + Claude)
1. Start (same throttle as the end of 10-13):
   `cd regen-engine && REGEN_MAX_PER_DAY=150 REGEN_TABS=4 REGEN_ASHBY_PER_PASS=2 REGEN_LOOP_MIN=3 REGEN_SOURCES_EVERY=10 docker compose -f deploy/bank.compose.yml up -d --scale applier=1`
   (the supervisor scales appliers 1..7; first pass is a full ~5,100-board scan, ~4 min; later passes are hot boards).
2. Health: `docker exec deploy-supervisor-1 python -m engine fleet`; UI http://127.0.0.1:3000/control (Containers,
   Reach list, Benchmarks cards) and **http://127.0.0.1:3000/reach** (the user's Workday/iCIMS fill page).
3. Run manual engine commands **as the engine user** in the pipeline container:
   `MSYS_NO_PATHCONV=1 docker exec deploy-pipeline-1 python -m engine <cmd>`. The supervisor runs as root (Docker
   socket): anything run there writes root-owned bank files and the pipeline then fails with EACCES. IMAP commands
   need the supervisor's .env: `docker exec -u 10001 -e HOME=/home/regen deploy-supervisor-1 python -m engine inbox --imap 3`.
4. Git: `main` on GitHub = local `main` (fast-forwarded 10-14 after CI). Keep merging by fast-forward (`git push
   origin main` once CI on the branch is green): a merge in GitHub's UI stamps the user's personal Gmail as committer
   (it happened again on PR #11: 10e9b99 and its parents). Commit email must stay the noreply one.
5. Code is baked into the image: after a change `docker compose -f deploy/bank.compose.yml build` (pipeline/appliers/
   supervisor share regen-applier:local) then `up -d --no-deps --force-recreate <services>` while appliers are idle
   (fleet: claimed 0, no `state=applying`).

## Done 10-13 (CHANGELOG [Unreleased] v0.13)
- Discovery: SmartRecruiters / Workday / iCIMS adapters (+2.5k boards; 5,094 total), reach list (`engine reach`,
  pipeline runs it every pass), LinkedIn alert mail over IMAP (supervisor, hourly), newgrad + GitHub feeds every 10th pass.
- `/reach` page: posting link, resume preview + download (`/api/resume/<f>?download=1`), fill kit (`/api/reach/kit`,
  presets + Fact Bank), per-job salary (posted range midpoint), mark submitted/skipped/undo (`/api/reach/mark`,
  `reach_mark` + `application` events; undo = status RESET). Narrow write switch REGEN_API_REACH=1 in the bank.
  Verified in the browser: PDF 200, download is an attachment, copy works (execCommand fallback), skip + undo reach the ledger.
- Supervisor: container inventory (`workspace/containers.json`, /control), benchmarks every 6 h (`engine bench --save`),
  daily jobs and alerts run as uid 10001.
- Inbox: decoded bodies from All Mail (about 30 rejections had been stored as confirmations), new rejection wordings,
  conditional "if not selected" stays a confirmation, latest-per-msg_id + `void` retractions (events.read and the
  Postgres `outcomes` view), own sent mail / newsletters ignored, company matched on sender+subject first.
- Fit gate from the 39-rejection review (memory `rejection-learnings`): years-in-field, sales-track blocker,
  NOT_ENGINEERING titles, region-duplicate role keys. B7: catch 9.1% -> 18.2%, cost 1.1% -> 2.2%.
- Forms: Greenhouse Employment block (Fact Bank current role), Ashby region-only location + radio groups outside
  field entries + "If other" boxes; arbitration at one crypto exchange (user-approved for that employer only) -> 2 submitted.
- Numbers: 165 submitted to date (96 with proof still on disk), 11 verified on 10-13, 38 rejections, 1 OA (a game company, old).

## Next (in order)
1. Throughput is supply-bound, not speed-bound: each pass finds 2-3 jobs that pass every gate; the queue is ~75%
   Ashby (1-2 per pass to avoid its bot check). Watch for an Ashby flag at 2/pass (`workspace/ashby_cooldown`); one
   "no confirmation seen (captcha?)" appeared right after raising it. If more show up, set REGEN_ASHBY_PER_PASS=1.
2. Workday / iCIMS **form filler** (the reach list has 84 jobs waiting on the user). Needs the user's candidate
   account per tenant: design it as "user signs in once in the applier's browser profile, engine fills".
3. Lead roles: 3 of 3 rejected (user chose to allow them; report the number again, don't gate without asking).
4. HANDOFF item from 10-12 still open: supervisor guardrails (cpu/mem limits per created container, inventory
   allowlist), evaluation container, wiki pages (Ledger, Data bus, Repo sync, Answer queue, MCP, Supervisor, Reach).
5. Inbox: run `inbox --imap 2` at session start (as uid 10001, see START 3) and review new rejections against their JD.

## Needs the user
- **A storage-hardware employer** (5 roles): "Does the deemed export rule affect your employment?" Yes/No. Claude recommended **Yes**
  (a non-US national is who the rule covers); the user's first reply ("Indian citizen so I'm good") read it the other way.
- **Reach list**: 84 Workday/SmartRecruiters jobs with resumes at /reach (user submits, then clicks "I submitted it").
- Gmail drafts from outreach (nothing sent); the 10-12 list of three to delete still stands.
- GitHub setting "Keep my email addresses private" (+ block pushes that expose it) is still not on: merges in the
  GitHub UI keep stamping the personal address.

# Handoff: 10-12 night session (~00:15 10-13). Stack is DOWN (volumes kept).

## START HERE
1. Start: `cd regen-engine && REGEN_MAX_PER_DAY=150 REGEN_TABS=4 docker compose -f deploy/bank.compose.yml up -d --scale applier=1`
   (services: postgres, ledger, api, web, mcp, answers, reposync, relay, pipeline, supervisor, applier; supervisor scales 1..7).
2. Health: `docker exec deploy-supervisor-1 python -m engine fleet` (services api/web/mcp/ledger/postgres/answers/reposync in its beat).
3. Look: control room http://127.0.0.1:3000/control · API + live DB browser http://127.0.0.1:8787/ (/db) · relay http://127.0.0.1:8799/
   · MCP http://127.0.0.1:8790/mcp (`.mcp.json` entry `regen-bank`) · public https://regen-engine.onrender.com
4. **Git workflow changed: commit locally, do NOT push main.** The reposync container (every 15 min) runs privacy scan + tests on
   local `main`, pushes `bot/sync`, opens/updates the PR (PR #11 open, Auto-fix on). User merges. Feed -> gh-pages automatically.
   Token: git-ignored `.gh_token` (fine-grained, Contents + PRs RW, verified). Postgres password: git-ignored `.pg_password`.
5. Local commits not yet on GitHub at shutdown are pushed to bot/sync by the last reposync pass (check PR #11).

## Done 10-12 (all in CHANGELOG [Unreleased])
Postgres ledger (views per kind, NOTIFY bus, ~1 s to browser, no web proxy); MCP oversight (fleet/kill/clear/audit/quarantine/scale)
+ in-bank HTTP MCP with ledger, answer-queue and reposync tools; kill switch per step; stricter leak guard (resume PDFs, outreach
drafts); retention (proof 90 d, logs 14 d, codes 1 d) hourly in supervisor; company_slug/role_key; daily HN + outreach (20 new/day,
dedupe); hot-board scans; drain handshake (fixed applier killed mid-batch); service probes/restarts; web container; reposync;
answer queue + `answers` container (fixed: /needs answers never reached containers); API home page (request tracker + DB browser,
filters, CSV/JSON); relay status page; Fact Bank crash + memory graph deep-layer fixes; error boundary; ERROR jobs retried once.

## Next (user's list, in order)
1. Verify MCP HTTP end to end with a real client (initialize + tools/list against 127.0.0.1:8790/mcp; GET returns 406 = alive).
2. Supervisor strict guardrails: every created container bounded (cpu/mem limits, labels, max count per service, TTL), tracked
   in an inventory, refuse anything outside the allowlist of services; audit + tests.
3. Evaluation container: benchmarks (B1-B7 + new: fit-gate precision, ATS read-back, code latency, supervisor decisions/drain
   correctness, bus latency, API p95) on a schedule/when commits land; autoscaled 0..N by the supervisor; results in Postgres + page.
4. README + wiki pages for all of the above (Ledger, Data bus, Repo sync, Answer queue, MCP levels, Supervisor).
5. SmartRecruiters adapter; Gmail cleanup (needs the user's OK on the exact search).

## Tell the user
- 33 Gmail drafts (nothing sent); delete Duets (malformed address), Furtim Modus (agency), "Early-stage Startup" (personal gmail).
- 6 verified 10-12 (stack was off until 22:00). Old proofs older than 3 days were already deleted by the previous policy.
- Ledger `ts` digits are local wall-clock (stored as UTC instants); the explorer shows them as local.

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
