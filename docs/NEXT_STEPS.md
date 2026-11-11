# REGEN: instructions for the AI operating the engine (before v2.0 ALIVE)

Status: ACTIVE since 2026-11-07 (added by the user). Followed strictly; v2.0 ALIVE is on hold until §9 is met.

Read this at the start of every session, before docs/HANDOFF.md. It overrides the HANDOFF "NEXT SESSION" order
until every exit criterion in §9 is met. v2.0 ALIVE (docs/ALIVE_PLAN.md) is **on hold** until then.

## Why the order changed

The engine works: 424 verified submissions. What it was built to do has not happened yet: the mail record shows a
handful of assessments and no interviews (Metrics 10-22: 282 sent → 80 rejections, 4 OAs; HANDOFF 11-01 onward:
8 confirmations, 10 rejections, 0 OA / interview). A new interface will not change that number. Until the engine
shows that it moves interviews, the job is **measure, target, reach people**, not ship more volume or more visuals.

The single number that matters from now on: **interviews (and OAs) per 100 verified applications**, reported
alongside every other metric.

## 0. Rules that don't change

- Truth: generated text only rewords Fact Bank entries and presets. Never add a claim the user can't back.
- No CAPTCHA solving, no bot-detection evasion, no account creation, no credential entry.
- Privacy gate clean on every commit. No company names from real applications in code, docs or tests.
- One task per session. Stop cleanly at 80% of the usage limit (gear N, drain inbox and claimed, `compose stop`).
- **Ask the user before** anything that can't be undone or that speaks for them in a new way: changing a preset
  answer, raising Shadow's mode or level, sending anything, deleting data, force-pushing, rewriting history.
- When a step below says "user decides", set out the options with evidence and stop. Don't pick for them.

## Decisions made by the user (11-07): don't ask these again

- **Scope rule:** "next steps" means resolving existing issues, **never deleting features**. Turn things off by
  default, gate them, or measure them; don't remove code, modes, pages or the Shadow brain.
- **§1.1: option (a).** `REGEN_JD_KEYWORDS` defaults to off (keywords.py line 73 default "1" -> "0"); the feature
  and the flag stay, so it can be switched on per run or for the §3 experiment. README "Never bluffs" claim stays.
  Add the guard test (README wording matches the flag default, and validate() covers every PDF text block when
  the flag is off).
- **§5: default mode `calls`.** Make `calls` the default (shadow.py settings fallback, now "off", and the live
  setting in the volume, now `autopilot`). **Keep `autopilot`** as a mode the user can engage on demand. **Keep the
  Shadow brain** (shadow_brain.py, ladder, training): it will be enhanced as we go. The never-answer list (work
  authorization, sponsorship, attestation, criminal history, salary) applies in every mode, with a test.

- **§1.1 follow-up (11-09): the line is the user's choice at every engine start.** Each start, ask the user "Role
  Keywords on or off for this run?" and run `python -m engine keywords on|off` (in the pipeline container, uid 10001).
  Never switch it on unasked; a clean stop switches it off again.

## Progress

- 11-09: **§1.1 done** (default off, per-run switch, guard test `tests/test_truth_claims.py`, README note).
- 11-09: **§1.2 done** (`python -m engine report rate`, Wilson interval, README stats row + wiki Metrics, guard test
  `tests/test_funnel.py`).
- 11-09: **§2 done** (`python -m engine report funnel`, splits + intervals; resume event now logs ats / posted /
  keywords_on). Labeler hand-check: 30 random labeled mails + every positive label. Confirmations 16/16 right by
  subject; rejections (14) carry neutral subjects, so precision needs bodies (not checked); OA labels 6/6 are real
  assessment mails BUT all from one employer and tied to 6 roles, which had inflated the rate to "5 OAs / 1.2 per
  100" and faked a tier-2 signal. Fixed (one positive per employer). True reading: 443 verified, **1 OA, 0 interviews
  = 0.2 per 100 (0.0 to 1.3)**; no split differs. Unlabeled-reply recall not measured yet (needs an IMAP pass).
- 11-09: **§5 done**: default mode `calls` (code + live volume), never-answer list in every mode with tests
  (tests/test_shadow.py). Weekly Shadow precision in wiki Metrics still to add.
- 11-09 night: **§4 done** (code): the supervisor's daily run now writes `outreach 7` (tier1 / sponsor / startup notes,
  nothing sent); `python -m engine outreach sent <company> [role]` logs a note the user sent (event `outreach_sent`);
  `report funnel` splits outreach into sent / drafted / none. Referral list still to propose to the user.
- 11-09 night: **§6 built**: `python -m engine try resume.pdf|.txt` (engine/try_it.py, stdlib + optional pypdf): reads
  the resume, scans 40 sample Greenhouse boards, runs the default fit gate, prints the top 10 with reasons and the
  blocked counts; read-only. 25 boards / 6,135 postings in ~2 s on the dev machine. README tip at the top. Clean machine (python:3.12-slim,
  nothing installed): 2 s to the first result; written in wiki Running.
- 11-09 night: **§3 decided** (user: "use the defaults") and partly built: engine/targeting.py reads
  profile/targeting.json (defaults daily_cap 15, tier_first on, skip_unsure on, keywords_ab off, ab_per_arm 150);
  select() stops at the cap (submitted + in flight) and puts tier1 / sponsors first, then freshest. Still to build:
  skip_unsure in the fit gate, and the Role Keywords A/B by URL hash (then switch keywords_ab on; 150 per arm before
  reading).
- 11-10: **§3 skip_unsure built.** The fit gate knows hard blockers only; batch.build() now also skips a blocker-free
  posting when the Fact Bank covers fewer than 5 of its terms or under 40% of them (covered / (covered + JD tech
  terms the bank lacks)). Both thresholds live in profile/targeting.json (unsure_min_terms, unsure_min_share); the
  skip is SKIPPED "JD: unsure fit: ..." so the funnel counts it. On the 93 past submissions with a stored JD it
  would have skipped 4 (~4%); 1 of those 4 vs 16 of the other 89 were rejected: far too few to read, so the numbers
  are a judgment call, not a learned rule. Tests 344 pass.
- Next: finish §3 (keywords A/B), then the small leftovers (§2 recall, §5 weekly precision, §4 referral list).

## 1. Make the public claims true (first session, small)

1. The README says every resume line comes from the Fact Bank and a validator rejects anything else. Since 11-05,
   `engine/tailoring/keywords.py` adds a "Role Keywords:" line of posting terms the Fact Bank lacks, and
   `resume.validate()` does not check it. **User decides**:
   - (a) Turn the line off by default (`REGEN_JD_KEYWORDS=0`) and keep the README claim, or
   - (b) Keep the line and reword the README, wiki Tailoring and Truthfulness pages, and CODING_STANDARDS §1.1 so they
     say exactly what the line is and that the user vouches for each term.
   Recommend (a) until §3 shows the line helps. Whichever is chosen, add a test that fails if the docs and the
   behavior disagree (e.g. assert `validate()` covers every text block that reaches the PDF, or that the README
   wording matches the flag's default).
2. Add the interview rate to the README stats row and to wiki Metrics, with its reproduce command. Show it next
   to "applications sent", never without it.

## 2. Build the outcome funnel (the measurement everything else depends on)

Use the existing pieces (`engine/feedback/rejections.labeled`, `outcome` events, `workspace/learnings.md`,
`python -m engine feedback --no-imap`, `python -m engine report`). Produce one report,
`python -m engine report funnel` (or extend `report`), with, for all verified submissions to date:

- Overall: sent → any reply → OA → interview → offer, with counts and rates.
- Split by: lane, ATS, employer tier (tier1 / tier2 / sponsors / other from profile/priority.json),
  hours from posting to submit (<6h, 6–48h, >48h), Role Keywords line present or not, answered_by (user / engine /
  shadow), and whether outreach followed.
- With ~400 submissions and very few positives, most splits will be noise. Print the counts, show a 95% interval
  (Wilson) for every rate, and **say plainly when a difference is not significant**, as the fit-gate learner
  already does. Don't let the report read as a finding when it isn't one.
- Confirm the mail labeler isn't missing interviews: hand-check 30 random labeled mails and every unlabeled reply
  from the last 30 days; record the labeler's precision/recall in wiki Metrics.

Commit the report code and a wiki section. Don't commit the user's outcome data.

## 3. Change the strategy from volume to targeting (user decides the numbers)

Propose to the user, with the funnel numbers from §2 as evidence:

- A daily submit cap (for example 10–15) in place of "as many as the gearbox allows".
- Selection order: sponsor tier and tier1 first, then freshest; skip roles where the fit gate is unsure instead of
  submitting and hoping.
- An experiment the funnel can actually read: alternate Role Keywords on/off by a hash of the posting URL, logged in
  the resume event. State up front how many submissions each arm needs before anyone looks at the result, and
  don't stop early because one arm looks ahead.

Make the agreed settings into presets / config, not code constants.

## 4. Put people in the loop: outreach

Cold applications are the weak channel; this is the one REGEN barely uses.

- Every day the engine runs: `python -m engine outreach 7`, then show the user the drafts for tier1 / sponsor /
  startup submissions, best first. Drafts stay truthful (only facts the same resume used). **Nothing is sent by
  the engine**; recipients are never guessed. The user sends.
- Log each sent note as an event (user marks it sent) so §2 can compare "applied + outreach" vs "applied only".
- Propose to the user a referral list: employers in profile/priority.json where they know someone. The engine
  tracks it; the user does the asking.

## 5. Shadow: back to "calls" until it earns more

Shadow is at ownership level L1 (19 held-out answers at 0.80; L2 needs 20 at 0.90) but runs in `autopilot`.

- Ask the user to switch the mode back to `calls`, explaining why: it is answering in their name on job forms
  below the bar the project set for itself.
- Whatever the mode: Shadow never answers work authorization, sponsorship, attestation / "I certify", criminal
  history, or salary questions on its own. Those park for the user. Add a test that enforces this list.
- Report Shadow's precision on the user's own later answers weekly in wiki Metrics.

## 6. Make a stranger able to try it (the quick start)

Right now a newcomer needs Docker, Postgres, Neo4j, a filled Fact Bank and an MCP client before anything happens.
Build a path to a first result in about 5 minutes, with **no database and no applying**:

- `python -m engine try resume.pdf` (or a paste box on the live demo): read the resume, scan a sample of boards,
  run the fit gate, and show the 10 best-fitting fresh roles with the reason each passed or was blocked.
- Standard library + one optional dependency at most. Document it at the very top of the README.
- Measure it: time from clone to first result on a clean machine, written down in wiki Running.

This is the step that turns visitors into users. The v2.0 visuals help bring people in; this is what makes them
stay.

## 7. Code health (only alongside the steps above, never as a separate rewrite)

- `engine/apply/runner.py` (~1,900 lines): when you touch an ATS, move that ATS's fill/submit into
  `engine/apply/<ats>.py` (as `workday.py` already is). One ATS per PR, form tests green before and after.
- `except Exception` (~100 sites): when you touch one, narrow it and add the "why it's safe to continue" comment
  that CODING_STANDARDS asks for. No sweeping change across files.
- Keep the test count and coverage in wiki Testing current; CI must stay green on every merge.

## 8. Repo hygiene

- docs/HANDOFF.md is a session log (~780 lines). Move it to `workspace/` (git-ignored) or keep only the latest
  entry in the repo; the rest goes to the changelog in one-line form. **User decides.**
- Trim CHANGELOG.md to releases; daily detail belongs in git history.
- The user's personal email appears as an author email in older commits (accepted in .privacy/accepted_history.txt).
  Tell the user; rewriting history is their call, never do it unasked.

## 9. Exit criteria: when v2.0 ALIVE may start

All of these, checked and written in the session's handoff:

- [x] README and wiki claims match the code (§1), with a test guarding it. (11-09)
- [x] Funnel report exists and the interview rate is in the README (§2). (11-09)
- [ ] The user has agreed the targeting settings and the experiment is running (§3).
- [x] Outreach drafts are part of the daily run and sent notes are logged (§4).
- [x] Shadow mode and the never-answer list are settled with the user (§5). (11-09)
- [x] The 5-minute quick start works on a clean machine (§6).

Then start ALIVE Phase 0 as written in docs/ALIVE_PLAN.md, and add "interviews per 100 applications" as a metric
the new interface shows prominently, not just applications sent.

## Session routine (every session)

1. Start or verify the stack (HANDOFF START command, `docker port deploy-api-1`, gear, `fleet_status`).
2. Read the funnel numbers since the last session. Tell the user if anything moved: a new OA, interview or reply.
3. Show the outreach drafts and anything parked on Needs you.
4. Do **one** item from the lowest unfinished section above. Test, commit, update the wiki.
5. Write the handoff: what changed, numbers, what's next, what is waiting on the user. Stop cleanly.
