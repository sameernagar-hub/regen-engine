# Handoff: 11-13 14:25 STOP POINT (user: everything off by 14:30). Stack STOPPED cleanly: gear N, inbox+claimed 0,
# cap 0, Role Keywords off, Shadow calls 5, `compose stop`, ledger ends on a full line. 6 submitted today.
# DONE since 14:10: Gearbox page (web :3000) has a Governor panel (ceiling/running/queue/target, memory/CPU/timeouts/
#   daily-cap gauges, reasons); /api/control/gearbox carries the snapshot; proxy dataset + lib/proxy.ts demo it.
#   Unpushed history rewritten (backup/pre-scrub-20261113) so no private employer name reaches GitHub; the old
#   flagged gauge-element blobs already on public main are pre-existing (CI --ci checks tree + new commits only).
# NEXT (user asked, not done): read README + wiki thoroughly and fix stale content (governor, titles, Airtable,
#   test count 378+), push bot/sync (force, rewritten) -> CI -> fast-forward main (`git push origin main`, POSIX
#   python shim on PATH), Render auto-deploys main: check https://regen-engine.onrender.com/gearbox. Then delete the
#   backup branch.

# Handoff: 11-13 ~14:10 RUNNING. START done; gear 3 -> 2 (7 appliers held the VM at 6.7/7.6 GB, a Page.goto
# timeout), cap 4 (150/day), Role Keywords ON, Shadow autopilot, MCP write on. Sources: boards harvest (+~170),
# recheck (10 back), scout (+373 boards), feed 51, newgrad 30 (Airtable fix 8573970: `urlWithParams =` layout).
# GOVERNOR (engine/governor.py): the supervisor re-judges the fleet ceiling EVERY pass from VM memory (measured
#   applier size, 2 GB reserve), CPU load (hold >70%, shed >95%), page/browser timeout share (last 30 min), the
#   daily cap, ramping +1 per 120 s and shedding -1 per 90 s (drain handshake). Gear = allowed range, supply = useful,
#   governor = safe. Snapshot: workspace/fleet/governor.json, `engine governor`; `supervisor` govern events on change.
#   Bench scenario scale_up_to_backlog now expects 1 create per pass. Pipeline container still on the pre-governor
#   image (recreate at a quiet moment; the Airtable fix was docker-cp'd into it).
# Volume: domains.json (bak-20261113): + associate/junior/graduate, UI/UX/graphics/growth/search/API/distributed/
#   storage/observability/web3/evals/platform/payments/data-infra engineers; quality/test titles software-only
#   (bare Quality/Test Engineer, supplier/shift QA, hardware systems test, client/customer support out).

# Handoff: 11-12 ~20:00 STOP POINT (user asked). Stack STOPPED cleanly: gear N, inbox+claimed 0, cap 0, Role Keywords
# off, Shadow calls 5, `compose stop`, volumes kept; events end on a full line, no tmp. All images built with cfdc07a.
# Run 18:40-20:00 (gear 3, cap 150, keywords on, keywords_ab now OFF, Shadow autopilot): 44 submitted. Confirmation
# mails go to a Gmail label by the user's own filter (not the inbox): check there, not the inbox.
# DONE: resume vocabulary noise fix + awards/publications + JD-relevant page fill (8bd4750); forward-deployed solutions
#   title (e2d01c2); rejection reason + level-aware selection (0de82a8); sponsorship NOW-only answers from the derived
#   preset + regression test (db27c54, 31728cc); text proofs, no screenshots, proof_file() accepts .txt for old .png
#   paths (2520be3, e00f11e); proof/ 450 MB -> 2.3 MB (non-submission screenshots deleted, submission ones converted to
#   .txt); inbox catches AI-led / video interview invites and short punctuated employer names (cfdc07a).
#   Volume: Fact Bank contact + teaching dates, domains.json widened then tightened (bak-20261112), unsure 3 / 0.3.
# NEXT: START -> gear 2/3 -> ask keywords on/off -> backfill reasons for old rejections via IMAP -> ALIVE Phase 1b.

# Handoff: 11-12 ~00:10 STOP POINT (80% of the Claude 5-hour limit). Stack STOPPED cleanly: gear N, inbox + claimed 0,
# cap 0, Role Keywords off, Shadow calls 5, `compose stop`, volumes kept. 6 submitted 11-11. Scout added +70 boards.
# ALIVE: plan proofread as one system (565e148); Phase 1b started: drivetrain parts open their rooms (65919be).
# NEXT: START -> gear 2 -> (A/B on: keywords decided per posting) -> CLEANUP pass (memory cleanup-every-session: dead
# piston code Cylinder/Chip/ghost layout, old proofs/resumes/logs/.bak files, Gmail clutter; confirm each new
# category) -> rest of Phase 1b (beads on coils, trail under flywheel, mobile circuit, V9 on wires, CPU check).

# Handoff: 11-11 ~23:58. Stack UP: gear 2, cap level 2 (50/day, user), Shadow AUTOPILOT + Role Keywords ON (user;
# the keywords A/B is still on and decides per posting). New container `scout` (engine/discovery/scout.py, every 3 h:
# GitHub job lists, public job APIs, new employer names probed; `engine scout --report`); round 1 = +70 boards.
# Shadow fix 89fd49d (abstains on form helper text); bad answers.json entry removed (bak-20261111).
# ALIVE (web-alive :3001 ONLY; web :3000 untouched): Phase 2 seat/captions a9bb909, Phase 3 trail+proof a3b696f,
# Phase 5 part 1 rooms b8341a1, scroll fix + pulse strip 6c676b3, ELECTRIC DRIVETRAIN 83a61b3 (user rejected the
# piston radial; picked concept A). NEXT SESSION FIRST: full proofread of docs/ALIVE_PLAN.md as one integrated system
# (§0 north star, §0a drivetrain), re-map Phases 3-6 + Track B onto the circuit, then continue. CLEAN STOP also: cap 0,
# keywords off, shadow calls 5.
# Supply note: queue is mostly Workday (yours) + Ashby (cooldown after a bot check); fillable = Greenhouse/Rippling.

# Handoff: 11-10 ~22:30 STOP POINT (user, near 80% of the Claude 5-hour limit). Stack STOPPED cleanly: gear N,
# inbox + claimed 0, Role Keywords off, cap level 0, Shadow calls 5, `compose stop`, volumes kept; events end on a full
# line. The Role Keywords A/B (keywords_ab) stays ON across runs by design. 7 verified submissions today.
# UI SPLIT (3e61434): `web` (:3000) is back on the released v1.x home (NEXT_PUBLIC_ALIVE=0); the ALIVE revamp runs in
#   its own `web-alive` container on http://127.0.0.1:3001 (regen-web-alive:local, ALIVE=1). API CORS allows both;
#   supervisor DECLARED has web-alive. All images are built with today's commits.
# START: the START command below brings up web-alive too; then `docker port deploy-api-1`, gear 2, and (A/B on) tell
#   the user the per-run Role Keywords question is decided per posting by the A/B.
# NEXT: ALIVE Phase 1's open check (10 min live flow + DevTools CPU < 15%, in a tab the user keeps visible: the
#   app's Browser pane hides when Claude's turn ends), then Phase 2 (Shadow co-driver). Build revamp work into
#   web-alive only: `compose build web-alive` + `up -d --no-deps --force-recreate web-alive`.
# Local commits since the last push: 6cd1ab6..3e61434 + this handoff -> reposync PR.

# 11-10 ~21:35: ALIVE PHASE 1 BUILT (5683029): the living engine home at http://127.0.0.1:3000/ (NEXT_PUBLIC_ALIVE=1 in
#   bank.compose.yml; set "0" + rebuild web to roll back). V9 pass (cold 18 s / warm 4 s), 375 px pass, reduced
#   motion rules loaded. Open: the 10-min live-flow/CPU check row in docs/bench/alive.md; then Phase 2 (Shadow
#   co-driver). Gotcha: CSS class names are global; the old home's .crank/.piston animate anything with those names.
# 11-10 ~21:10: ALIVE PHASE 0 DONE (5328097): typed events + Signal SSE + /api/signals, emitters (apply_start, shadow
#   abstain + conf, problem lights), engine/live/replay.py (`engine replay`), apps/web/lib/spine.ts folded in
#   useEngine().alive, scripts/bench_alive.py (V6/V7/V8/S1 pass; docs/bench/alive.md row). All containers on the new
#   image. NEXT: ALIVE Phase 1 (the living engine home), docs/ALIVE_PLAN.md §5.
# Handoff: 11-10. Stack UP (gear 2, Role Keywords ON and cap level 2 = 50/day, both by the user's choice for this run).
# §3 skip_unsure built (targeting.unsure() called from batch.build(); thresholds unsure_min_terms 5 / unsure_min_share
#   0.4 in profile/targeting.json). §3 A/B built: keywords_ab (targeting.json, off) -> URL hash picks the arm, logged as
#   ab_arm; `engine report ab` hides rates until 150 per arm. CLEAN STOP also runs `engine cap 0`.
# REVAMP READINESS (11-10): §5a API routes built + tested (61663ec): /control/keywords|cap|targeting, /report/rate|
#   funnel|ab, POST /outreach/sent (only public POST /try left, for Phase 5). openapi.json (56 paths) + api.d.ts
#   regenerated, `npm run typecheck` clean, 348 tests pass. All images rebuilt; api, pipeline and appliers recreated.
#   ~21:00 the user switched keywords_ab ON: NEXT_STEPS §9 is ALL TICKED -> next session starts ALIVE Phase 0
#   (docs/ALIVE_PLAN.md §5). The A/B stays on across runs (a clean stop does NOT turn it off; the per-run keywords
#   question no longer decides while it is on). `engine report ab` shows only counts until 150 per arm.

# CAP SWITCH (user 11-09): `python -m engine cap [0|1|2|3|4|up|down]` = 15 / 25 / 50 / 100 / 150 per day, stored as
# cap_level in profile/targeting.json and read live. Every start begins at level 0; a clean stop runs `engine cap 0`.
# Handoff: 11-09 ~22:40 STOP POINT. Stack STOPPED cleanly at ~75% of the Claude 5-hour limit (gear N, inbox +
# claimed 0, Role Keywords OFF, Shadow back to `calls`, `compose stop`, volumes kept; events end on a full line, no
# tmp files). Images ALREADY rebuilt with c7c2a36: the next START runs the targeting cap.
# §3 DECIDED by the user ("use the defaults"): engine/targeting.py + profile/targeting.json (file optional; defaults
#   daily_cap 15, tier_first on, skip_unsure on, keywords_ab off, ab_per_arm 150). select() stops at the cap
#   (submitted + in flight) and orders tier1 / sponsors first, then freshest. REGEN_MAX_PER_DAY stays the runner backstop.
#   STILL TO BUILD: skip_unsure in the fit gate; Role Keywords A/B by URL hash (log the arm in the resume event, then
#   keywords_ab on; read only after 150 per arm). Expect ~15 submits/day now: that is the decision, not a fault.
# Then the leftovers: §4 referral list proposal, §2 unlabeled-reply recall, §5 weekly Shadow precision in wiki Metrics.
# Local, not pushed: regen-engine 9c02261, 5b960ed, 1765547, c7c2a36 + this (reposync PR); wiki ba32158.

# Handoff: 11-09 ~21:55. Stack is UP (started ~21:33 after `compose build`), gear 2, Role Keywords ON and Shadow
# AUTOPILOT for this run (both by the user's choice; the §5 never-answer list still parks work authorization,
# sponsorship, attestation, criminal history and salary questions for the user). Images rebuilt with 9c02261;
# supervisor/pipeline/applier recreated on it. CLEAN STOP: gear N, wait for inbox + claimed 0, `engine keywords off`,
# `engine shadow calls 5` (the default), `compose stop`, verify, write this block.
# Done tonight: §4 (9c02261): daily run writes `outreach 7`; `engine outreach sent <company> [role]` logs a note the
#   user sent (event outreach_sent); `report funnel` splits outreach sent / drafted / none. 13 drafts in
#   workspace/outreach/drafts.json (3 tier 1, 9 tier 2, 1 startup), nothing sent.
#   §6 (5b960ed): `python -m engine try resume.pdf|.txt` (engine/try_it.py): 2 s on a clean python:3.12-slim; README
#   tip; wiki Running ba32158 committed locally, NOT pushed.
# Left before ALIVE: §3 (USER DECIDES: daily cap, tier1/sponsors first then freshest, skip unsure fits, Role Keywords
#   A/B by URL hash), §4 referral list proposal, §2 unlabeled-reply recall, §5 weekly Shadow precision in wiki Metrics.
# Rate: 446 verified, 1 OA, 0 interviews (0.2 per 100). Tests 337 pass.

# Handoff: 11-09 ~16:50 STOP POINT. Stack STOPPED cleanly at ~77% of the Claude 5-hour limit (gear N, inbox +
# claimed 0, Role Keywords switched OFF, `compose stop`, volumes kept; events end on a full line). Shadow mode = calls.
# Image regen-applier:local is NOT rebuilt with 93a13d9/58600ff: run `docker compose -f deploy/bank.compose.yml build`
# before START, or the containers lack `engine keywords`, `report rate/funnel` and the §5 never-answer list.
# The user wants ALL NEXT_STEPS §9 items done so v2.0 ALIVE can start; still open, in this order:
#  §4 outreach: add `outreach 7` to the daily run (supervisor already runs HN outreach daily) + a way for the user to
#     mark a note SENT (event `outreach_sent`), and show "applied + outreach" in `report funnel`.
#  §3 targeting: USER DECIDES. Evidence: 443 verified, 1 OA, 0 interviews (0.2 per 100); no split differs. Propose a
#     daily cap (10-15), tier1/sponsors first then freshest, skip unsure fits, and the Role Keywords on/off experiment
#     by URL hash (state the per-arm sample size up front). Settings go in presets/config, not code.
#  §6 quick start: `python -m engine try resume.pdf` (no DB, no applying): read resume, scan sample boards, fit gate,
#     top 10 roles with reasons; stdlib + one optional dep; time it on a clean machine, write it in wiki Running.
#  Small leftovers: §2 recall on unlabeled replies (IMAP pass); §5 weekly Shadow precision row in wiki Metrics.
# Run 11-09 16:02-16:48 (gear 3, Role Keywords ON by the user's choice): 479 submitted total (+20 this run).

# Handoff: 11-09 ~16:30. Stack is UP (started 16:02), gear 3 at the user's request ("apply as much as possible"),
# Role Keywords ON for this run (user's choice). Shut down cleanly at 80% of the Claude 5-hour limit.
# NEXT SESSION, in this order:
# (0) Read docs/NEXT_STEPS.md FIRST (its "Progress" block says where we are: §1 done, next is §2).
# (1) START command below, `docker port deploy-api-1`, shift to gear 2 (3 if the user asks), `fleet`.
# (2) ASK THE USER: "Role Keywords on or off for this run?" then
#     `MSYS_NO_PATHCONV=1 docker exec -u 10001 deploy-pipeline-1 python -m engine keywords on|off`. Never on unasked.
# (3) `python -m engine report rate` (the interview rate), outreach drafts + Needs you, then the next NEXT_STEPS item.
# CLEAN STOP: gear N, wait for inbox + claimed 0, `engine keywords off`, `engine cap 0`, `compose stop`, verify, write this file.
# v2.0 ALIVE stays ON HOLD until NEXT_STEPS §9 is all ticked. The user wants the next steps finished first.

## Done 11-09
- NEXT_STEPS §1.1 (38af39a): Role Keywords off by default; per-run switch `engine keywords on|off`
  (workspace/keywords.json, read live by every container; REGEN_JD_KEYWORDS=0/1 wins); build() prints the line only
  while on; guard tests tests/test_truth_claims.py. README "Never bluffs" row carries a one-clause note.
- NEXT_STEPS §1.2 (a1df575): `engine report rate` (engine/feedback/funnel.py: wilson(), verified(), outcomes(),
  rate()). First reading: 426 verified, 5 OAs, 0 interviews = 1.2 per 100 (95% interval 0.5 to 2.7). README stats row
  + wiki Metrics show it. Wiki Metrics edit is committed locally in ../regen-engine.wiki, NOT pushed (ask the user).
- Tests 310 pass. Image rebuilt with a1df575; the running pipeline still runs the older image (Role Keywords on by
  default there, the same as the switch being on). The next `up -d` recreates the containers on the new image.
- Mail since 11-07: 14 rejections, 4 confirmations, no OA / interview. 9 outreach drafts ready (2 tier 1, 7 tier 2)
  in workspace/outreach/drafts.json: nothing sent, the user sends.
- Bot PR 31 is merged. Local commits f4a4359 and earlier + today's two -> reposync PR.

## Done 11-09 (later)
- §2 report (`engine report funnel`). Hand-check found the "5 OAs" were ONE employer's mail tied to 6 roles; fixed:
  1 OA in 443 = 0.2 per 100, no split stands out. README + wiki corrected. The resume event now logs ats / posted / keywords_on. Tests 312 pass.

## Next
- §2 remainder: the labeler hand-check (see NEXT_STEPS Progress). Then §3: show the user the tier evidence.
- (done) §2: `engine report funnel` on top of funnel.py: sent -> any reply -> OA -> interview -> offer, split by lane, ATS,
  employer tier, hours from posting to submit, Role Keywords on/off (resume event `jd_keywords`), answered_by,
  outreach; Wilson interval on every rate, "not significant" said plainly. Then the labeler hand-check (30 random
  labeled mails + every unlabeled reply of the last 30 days) with precision / recall in wiki Metrics.
- `engine learn` "By ats" table groups by URL substring and puts almost everything under one ATS: use the job's
  `ats` field in the funnel instead.
- Shadow is still in `autopilot` in the volume; §5 (decided: default `calls`) is not done yet.

# Handoff: 11-07 ~23:45. Stack is STOPPED cleanly (gear N, inbox + claimed 0, `compose stop`, volumes kept).
# Verified after stop: no temp files, events.jsonl ends on a full line, queue/gear/answers/presets JSON whole.
# NEXT SESSION, in this order (changed 11-07 by the user; follow strictly):
# (0) Read docs/NEXT_STEPS.md FIRST. It overrides this order until its §9 exit criteria are all met.
# (1) START command below, `docker port deploy-api-1`, shift to gear 2, `fleet_status`
# (a "Gmail tab" warning right after start is a race; IMAP codes run in the supervisor). Close bot PR 31 if empty.
# (2) NEXT_STEPS session routine: funnel numbers since last session, outreach drafts + Needs you, then ONE item
# from the lowest unfinished section. First item: §1.1, user chose (a): flag default off + guard test. Then §5 (decided:
# default `calls`, autopilot kept on demand, brain kept). See NEXT_STEPS "Decisions". Never delete features.
# v2.0 ALIVE (docs/ALIVE_PLAN.md) is ON HOLD; do not start Phase 0. Stop cleanly at 80% of the 5-hour limit.

## Prep for docs/NEXT_STEPS.md (read 11-07, so the next session starts without re-reading code)
- §1.1 Role Keywords: engine/tailoring/keywords.py (flag `REGEN_JD_KEYWORDS`, default **on**, line 73); printed in
  engine/tailoring/resume.py:168 from `spec["jd_keywords"]`. `validate()` (resume.py:112) checks skill_text, roles,
  facts, fact_pick, projects, skills, **not jd_keywords** -> the README "Never bluffs" row (README.md:31) is untrue
  today. Ask the user (a) default off or (b) reword README + wiki Tailoring / Truthfulness-and-Safety + CODING_STANDARDS
  §1.1; recommend (a). Guard test: validate() covers every PDF text block, or README wording matches the flag default.
- §1.2: README stats row is README.md:40 ("applications sent with proof"); wiki page Metrics.md.
- §2 funnel: `report` is an inline function in engine/__main__.py (cmd at line 171); `feedback` = engine/feedback/
  rejections.py; inbox/learn = engine/feedback/inbox.py; outcome events in engine/feedback/events.py. No Wilson helper
  in engine/ yet (fit-gate learner has the "not significant" wording to reuse). Outcome data stays out of git.
- §4: `outreach` = engine/outreach.py (MCP tool `outreach_drafts`). §5: engine/shadow.py MODES line 24, mode is
  `autopilot` now; never-answer list lives in shadow_brain.py:379 (+ override.blocked): extend + test in
  tests/test_shadow_brain.py. Mode change needs the user's yes.
- §7 sizes: runner.py 1,886 lines; 98 `except Exception` in engine/. §8 needs user decisions (HANDOFF location,
  CHANGELOG trim, old author email in history: tell, never rewrite).

## Done 11-07 night
- Restarted after the Docker shutdown; reposync recreated; gear 2; supervisor scaled 1 -> 3 appliers on demand.
- Run 22:42-23:42: 1 submitted, 13 NEEDS YOU (11 answered_by shadow, parked again), 27 skipped (fit gate).
  Supply-limited: later passes found nothing selectable. Pass 1: parked: a lending employer (location / familiarity), a robotics role
  (robotics "2+ yrs controls", honest no), one human verification (yours).
- v2.0 ALIVE plan written (docs/ALIVE_PLAN.md + wiki Revamp-v2); README cut to essentials pointing at the wiki.

# Handoff: 11-07 ~14:10. Stack is STOPPED. Docker Desktop was paused, then shut down, which SIGKILLed every container
# (exit 137; postgres exited cleanly). Checked afterwards: claimed 0, inbox 0, no temp files, every JSON whole, the
# event log ends on a complete line. gear.json set to N in the volume (backup gear.json.bak-20261107).
# Next start: the START command below, then `docker port deploy-api-1`, then shift to gear 2. Recreate reposync too
# (`compose up -d --no-deps --force-recreate reposync`): it ran the old feed check, which blocked the public feed on
# the words "remote" and "engine" (both now common words, commit below).
# Local commits 5f54c38 (feed airbag "remote") + 8e31ab7 (Shadow brain) -> reposync PR. Wiki 62983f0 pushed.

## Done 11-07
- Shadow brain (engine/shadow_brain.py): five strategies (bank, memory, TF-IDF neighbour, engine, yes/no), confidence
  = raw x per-(strategy, question type) Beta reliability, shape check, noisy-OR voting, abstains below tau. Trained and
  tested on the user's own answers (fixed 80/20 split, leave-one-out tuning, wrong costs 3x); hourly retrain in the
  answers tick; live feedback per strategy. First runs: test precision 0.60 -> 0.80, coverage 0.26, 0 violations.
- Ownership ladder L0-L5 + "nested agents" and the agent graph (engine/agents.py); actions run only when earned;
  supervisor takes Shadow's applier balance at L3. Shadow is at L1 (L2 needs 20 held-out at 0.90; has 19 at 0.80).
- Mode `autopilot` (set 11-07 at the user's request): inline answers, parked jobs picked up at once, no calls.
- /shadow: vision map, agent graph, how Shadow decides, training ground; front-page popup shows level + test score.
- Shutdown rule is now 80% of the Claude 5-hour limit (user, 11-07).
- Run 11:20-13:15: 1 submitted, 14 NEEDS YOU (mostly last night's Shadow retries parking again -> yours by rule),
  54 skipped (fit gate: 5+ yrs, citizenship, C#). Supply-limited: 0 of ~2,040 queued selectable, Ashby cooling down.

## Next
- Title filter let "Maintenance Tech Lead" through as backend (reach list only): tighten.
- Engine yes/no policy matched the user's own answers only ~35% ("N years of X"): consider bank-first for those.
- Parked for the user: employer-familiarity questions (one streaming employer, 6 roles; one lending employer), a
  distributed-systems self-rating, a robotics role's "2+ years" questions (tried 6x since 11-03), a CST/EST residence
  question (honest No from the home-city preset), one human verification.

# Handoff: 11-06 ~23:45. Stack is STOPPED cleanly (gear N, inbox + claimed drained, `compose stop`, volumes kept).
# On start: shift to gear 2. Shadow mode is "calls" (ring 5 min). main = pushed (Shadow commits 2a93985..892b121).

## Done 11-06
- Shadow (engine/shadow.py, wiki/Shadow): a parked job rings call 1, call 2, then Shadow retries it as the user.
  Shadow recommends at call 1, remembers (profile/shadow_memory.json + answer bank), learns from the ledger every
  5 min; your answers win. answered_by on every application; supervisor heartbeat `shadow`. /shadow page.
- The gate treats Shadow as the user (answers.save by="shadow"; legal answers job-scoped; EEO decline-only).
- Answer fixes: hereby certify, permanent address, start quarter/year, how-heard nearest option, gapped salary
  bands, HTML-escaped Greenhouse pay ranges. Front page: Desk/Shadow popups show live figures (no placeholder dot).
- Run 20:20-23:40: 11 submitted (7 + 3 engine + 1 Shadow), 28 jobs picked up by Shadow; most Shadow retries parked
  again on questions it could not settle truthfully, or hit Lever CAPTCHAs.

## Next
- Look at the Shadow retries that parked again (answered_by shadow, NEEDS YOU): which questions, and whether presets
  or Fact Bank entries would settle them truthfully.
- Desk: ~8 Lever CAPTCHA jobs from tonight (6 employers) are filled and wait for the user's click. Shadow never touches CAPTCHAs (hard rule).

# Handoff: 11-06 ~00:30. Stack is STOPPED cleanly (gear N, inbox + claimed drained, `compose stop`, volumes kept).
# On start: shift to gear 2. Local commits on main -> reposync PR.

## Done 11-05
- Resume builder (763a7ec, d7ba762): dense one page filled from a ranked reserve of Fact Bank bullets; 2-line summary;
  every JD keyword the page lacks goes on a "Role Keywords" line (keywords.py, uncapped, JD spelling kept).
- Fact Bank "variants": 91 one-line wordings of 42 facts, each leading with a different angle; tailor ranks them per
  JD, resume.fit prints the first that fits one line. role_prefix adds the teaching role. Backup fact_bank.json.bak-20261105.
- Feedback loop: resume.qa gate (pages, fill, wrapped bullets, duplicates); selftest.py hourly over recent JDs
  (batch holds if most fail; 7/8 pass at the start); learn.py weights wordings by OA/interview vs rejection outcomes.
- Title filter: software, AI and CS-related hardware only (no sales/solutions/support/analyst); domains.json in the
  volume (.bak-20261105); answer retries go through the filter too (cc74d85).
- 16 bank answers from presets (answers.json.bak-20261105). Run 21:00-00:30: 26 submitted, 76 NEEDS YOU, 76 skipped.

## Next
- Pending user: employer-familiarity questions (5 roles at one streaming employer), a past-employer confidentiality
  affirmation, a new-grad "<1 year experience" question, a distributed-systems rating, a W2 hourly rate, a human
  verification question, a motor/controls experience question; desk hCaptcha tick; one Ashby bot-check.
- Filler gaps: required cover-letter FILE upload; resume upload failed on two employers' forms.
- The appliers were not recreated on the newest image (only the pipeline/answers were): fine, tailoring runs in the pipeline.

# Handoff: 11-03 ~22:05. Stack is STOPPED (user: shut it down now): gear N, 4 batches were still claimed (supervisor
# requeues them on start), `compose stop`, volumes kept. On start: shift to gear 2. Local commits on main -> reposync PR.

## Done 11-03
- Tests 272 pass; all images rebuilt; /desk verified: the desk embeds and connects with no password prompt after
  the CSP fix (frame-src now allows the noVNC origin, next.config.mjs).
- Reposync was blocked by the privacy scan: handoff text named the user's city and employers. Scrubbed and squashed
  into the unpushed handoff commit. Rule: handoffs never name employers or the city (the scan also flags substrings,
  e.g. a CSS property containing a denylisted company name).
- 8 bank answers drafted from presets (answers.json.bak-20261103); 20 parked jobs requeued via answer_queue._retry
  (run with -e PYTHONPATH=/app -w /data/workspace). The local regen-engine MCP has writes OFF: edit answers.json
  in the volume instead.
- A "real V8" front engine was built and REJECTED by the user (pistons not joined to rods, cylinders overlapping,
  untidy). It was removed (commit dropped, never pushed); the earlier radial engine is live again.

## Next (front engine, the user's words: "the earlier version was good")
- Keep the earlier engine (apps/web/app/page.tsx, radial). Only fix: Desk and Gearbox must be clearly separate.
  Cause: 8 cylinders on a circle put cylinder 5 (Desk) at 90 deg, straight down, on the gearbox at GBX (600, 696).
  Smallest fix: rotate the ring by half a step (ang(i) = -90 + 22.5 + i*45) so no cylinder points straight down,
  or move the gearbox off the bottom axis; then check the Desk label and the Gearbox label do not touch (screenshot).
- Only if the user asks again for a V8: their picture is 4 cylinders on the left and 4 on the right, each bank in a
  straight row (left-right-left-right firing), pistons visibly joined to their rods, no cylinder overlapping another.
- Desk: the 9-10 YC fills listed on /desk are stale (the desk holds 1 tab); re-request them before telling the user to
  tick hCaptcha. Human checks waiting: ~189 (Ashby clicks, Lever CAPTCHAs). Deemed-export questions need the user.
- The user wants a warning near 90% of the 5-hour limit (get_usage); this session stopped at ~88%.

# Handoff: 11-02 ~22:40. Stack is STOPPED mid-batch (gear N, not drained; volumes kept). Local commits -> reposync PR.

## Done 11-02
- Started at gear 3, REGEN_MAX_PER_DAY=250 / REGEN_MAX=250 (6 appliers). Run 22:11-22:40: 0 submitted, 15 NEEDS YOU,
  27 skipped, 1 failed. Stopped early: the user's Claude session limit, not the machine.
- 9 parked questions answered from presets (relocation Yes, Master's / Computer Science, home city, no accommodation,
  essential functions Yes); backup answers.json.bak-20261102. Retry batch answers_20261102_221144 (16 jobs).
- Mail since 11-01: 8 confirmations, 10 rejections, no OA / interview.
- Commit 2ed8d6e: /desk page (apps/web/app/desk/page.tsx): the desk noVNC inline via the password-carrying
  /api/reach/desk `open` link (the user never types the VNC password; the password itself stays, it keeps other web
  pages off ws://127.0.0.1:6080), plus every hCaptcha / Lever CAPTCHA / Ashby human-click job with Open posting /
  Mark submitted / Skip. New POST /api/human/mark (records SUBMITTED / SKIPPED "by you"). Status text points to
  http://127.0.0.1:3000/desk. Front page: 8 cylinders, V8 firing order.
- CAPTCHA bypass was asked for and declined: human checks stay the user's (now on /desk).

## Next
- NOT BUILT OR TESTED: run tests, `compose build`, recreate api + web (appliers + pipeline when claimed is 0), open
  /desk in the browser: iframe connects, Mark submitted removes the row, the front-page engine renders 8 cylinders.
- On start: shift to gear 2 (gear 3 if the user asks). 5 claimed + 4 inbox run batches were left: check the
  supervisor requeues the claimed ones.
- The desk lost its 9 YC fills (names on /desk): re-request them (runner.ensure_resume + workday.request; run from
  /data/workspace, paths are relative).
- Pending user: 7 employer-specific questions (product familiarity, travel, AI opinion, ratings, a transcript upload,
  attention checks); see /needs.

# Handoff: 11-01 ~22:45. Stack is DOWN (gear N, drained, compose stop, volumes kept). Local commits on main -> reposync PR.

## Done 11-01
- Gmail review -> lessons: OPT/CPT sponsorship rejection wording (inbox), "does not engage in sponsorship" JDs (fit
  gate), bilingual / implementation-specialist / technical-consultant / sales-engineer titles are non-engineering.
  Two no-sponsor employers added to the volume's domains.json (names stay out of the repo).
- YC "US citizen/visa only" roles are dropped at discovery (33 of 40 queued YC roles); portal "Will sponsor" and
  venture-portal jobs get priority boosts.
- Filler: YC pages load on domcontentloaded (networkidle hung the desk), numeric/decimal range buckets (years, GPA),
  "(XX)" abbreviations match bare options. 10+ bank answers (backup answers.json.bak-20261101).
- Run 21:20-22:40: 7 submitted. Stuck: 19 parked questions, 19 JD-gated, 6 desk hCaptcha, 5 Lever CAPTCHAs.

## Next
- On start: shift to gear 2. The desk lost its filled YC tabs on stop (Drillbit, Legion Health, GhostEye, Evidence,
  Reframe): re-request them (`engine batch <name> <id>` then workday.request), then tell the user to tick hCaptcha.
- Never recreate the desk while it holds filled tabs.
- Throughput: parked questions are the bottleneck; ask the user for the repeating ones early in the session.
- Pending user: Sezzle transcript upload; Plaid AI opinion; Telnyx distributed-systems rating; PlayStation W2 rate.

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
