# REGEN v2.0 "ALIVE": one living engine (revamp plan)

Status: **ON HOLD** (11-07): docs/NEXT_STEPS.md comes first; Phase 0 starts only when its §9 exit criteria are
all met. PLAN, not started (written 2026-11-07). v1.x stays the released line; v2.0 ships when Phase 5 passes.
Wiki: [v2.0 Revamp](https://github.com/sameernagar-hub/regen-engine/wiki/Revamp-v2). This file is the build checklist.
Owner: the user decides; Claude builds phase by phase. Next session: start the engine, then follow docs/NEXT_STEPS.md.
One phase per session, at most. Every phase ends with a local commit (reposync opens the PR) and a stop.

## 1. Goal (one sentence)
The site *is* the engine: each part on screen is a real container, each motion is a real event, and each control
drives the real backend. You watch REGEN run instead of reading a dashboard.

## 2. Scope: fixed per phase, growing between phases

The plan is a living roadmap; each phase is a closed contract. **Scope can grow, but only between phases, through
the feedback model below.** A phase that has started never takes on new work.

### Track A: v2.0 core (ships v2.0 when Phase 5 passes)
- Typed live events + nightly replay recorder (Phase 0).
- Home `/` rebuilt as the living engine (Phase 1), Shadow co-driver (Phase 2), exhaust trail (Phase 3).
- Nav cut from 15 pills to 4 rooms as drawers + `/docs` (Phase 5). Old routes stay as deep links.
- Every NEXT_STEPS control and report on screen: Role Keywords, cap dial, targeting, funnel + rate, outreach
  "Mark sent", Shadow never-answer list, quick-start paste box (§5a; merged 11-09).
- "While you were away" replay (Phase 4) and live tab title/favicon (Phase 6).

### Track B: v2.x extensions (accepted 11-07, built after v2.0, each one a phase with the same rules)
| Phase | Idea | One-line scope | Depends on |
|---|---|---|---|
| 7 | Phone push for your-turn items | push only for CAPTCHA / abstained questions / outcomes needing action; never routine progress; reuse the engine's existing alert path, no third-party tracking | Phase 0 events (`human.check`, `shadow.abstain`, `outcome`) |
| 8 | Inner pages redesigned | one page at a time, in the order Your turn → Results → Garage; each page reads from `useEngine()` and goes live (no fetch-once pages left) | Phase 5 drawers |
| 9 | Shadow L2+ visuals | the seat grows with the ladder (L2 job agents, L3 supervisor balance...); each rung's visual unlocks only when the backend reports it earned | Phase 2, Shadow ladder |
| 10 | Engine sound pack | optional, off by default, muted on load: idle hum by gear, piston tick on fire, exhaust puff on submit; Web Audio, no files over 200 KB total | Phase 1 |
| 11 | Weekly replay highlights | a 60-second week in review from the recorded replays (best day, first interviews, Shadow's handovers); public version scrubbed | Phase 4 |
| 12 | 3D engine | the same 5-cylinder engine in 3D (one dependency allowed, chosen in the phase's design note); 2D stays as the fallback for low power and reduced motion | Phases 1-3 stable, V2/V3 budgets held |

### Feedback model: how new ideas enter (so nothing is lost and nothing derails)
1. **Capture:** any new idea goes into §8 "Idea inbox" with the date and one line. No code.
2. **Triage at phase boundaries only** (start of a session, before the next phase): each inbox idea becomes one of
   - **merge**: it fits an *unstarted* phase. Add it to that phase's file list + acceptance checks + V-bench.
   - **new phase**: added to Track B with scope, dependencies and its own checks.
   - **park**: stays in the inbox with the reason.
3. **Learning loop:** after each phase, its benchmark row and what went wrong (docs/bench/alive.md) feed the triage.
   A phase that missed a V target gets a fix-up phase before anything new.
4. The user makes the call on every merge/new phase. Claude proposes, and the wiki page is updated with the plan.

### Never (hard limits, not ideas)
- Fake activity, invented numbers, or motion without an event.
- Shadow touching CAPTCHAs; lowering ladder thresholds to unlock a visual.
- Engine behavior changes smuggled in as UI work (engine changes get their own commit and changelog entry).

### Stop rules (anti-wander)
- If a phase needs a file not listed under it, stop and write why in this doc before touching it.
- If a phase's acceptance checks don't pass after 2 attempts, revert to the last commit and report.
- Each phase is behind `NEXT_PUBLIC_ALIVE=1` until Phase 5 ships. Turning it off restores today's home.
- 80% of the Claude 5-hour limit → stop, commit WIP on a branch, update HANDOFF.md.

## 3. One entity: every part on screen is a real container

| Engine part (screen) | Container / source | Live signal it shows | Control it drives |
|---|---|---|---|
| Intake (top) | `pipeline` (discover stage) | `discovered` events → chips enter | — |
| Cylinder 1 **Listen** | `pipeline` | narration stage `listen` | — |
| Cylinder 2 **Judge** | `pipeline` fit gate | stage `judge` (skip falls out w/ reason) | — |
| Cylinder 3 **Write** | `pipeline` compose | stage `write` (`resume` events) | — |
| Cylinder 4 **Apply** | `applier-N` (one piston per live applier) | stage `apply`, fleet heartbeats | — |
| Cylinder 5 **Hear** | `feedback` + `supervisor` IMAP | stage `hear` (`outcome`) | — |
| Gearbox | `pipeline` gear.json | `gear` events | `/control/gearbox` (shift) |
| Co-driver seat | `answers` (Shadow tick) | `shadow` events, `application.by=shadow` | `/shadow` POST (mode) |
| Fuel tank | Fact Bank + queue supply | selectable jobs left | opens Facts drawer |
| Your-turn tray | `/api/human` + `desk` | `NEEDS YOU`, `human.check` | opens Your turn drawer |
| Exhaust trail | ledger (`postgres`/`ledger`) | `SUBMITTED` w/ proof | opens proof drawer |
| Warning lights | `supervisor` problems | `/control/fleet` problems | opens the matching drawer |
| Plug (MCP cord) | `mcp` :8790 | heartbeat up/down | opens MCP drawer |

The 5 narration stages already exist (`Stage = listen|judge|write|apply|hear`, apps/api/models.py:7). A 5-cylinder
radial is a real engine layout (radials use odd counts), so the engine gets *more* honest, not less.
A part whose container is down is drawn **cold** (grey, still) and its warning light comes on. That's the one-entity idea:
backend health is visible as engine health, with no separate status page.

## 4. Event contract (Phase 0 output, everything else depends on it)
Extend `Narration` (apps/api/models.py) with optional fields. Existing fields are unchanged, so old clients keep working:
```
kind:   "discovered"|"gate.pass"|"gate.skip"|"resume"|"apply.start"|"submitted"|"parked"|
        "shadow.answer"|"shadow.abstain"|"shadow.mode"|"human.check"|"gear"|"outcome"|"problem"|"problem.clear"|
        "keywords"|"cap"|"targeting"|"outreach.sent"          # NEXT_STEPS controls (§5a)
job:    str | null      # job id, so one chip can be followed across stages
company:str | null      # null on the public site (privacy: role + lane only)
by:     "engine"|"shadow"|"desk"|"you" | null
detail: str | null      # skip reason / parked question (shortened, privacy-scanned)
conf:   float | null    # Shadow confidence on shadow.answer
```
Source mapping in `engine/live/server.py:narrate()`: `application` status → submitted/parked/gate.skip;
`kind:"shadow"` action configure → shadow.mode, train → ignored; `kind:"gear"` → gear; `application.by=="shadow"` →
shadow.answer. New emitters (small, engine side): `apply.start` (worker claims job), `shadow.abstain` (shadow
leaves a question), `problem`/`problem.clear` (supervisor, only on change).

## 5. Phases (file lists are the whole allowed surface)

### Phase 0: event spine (backend ↔ frontend wire). Budget: 1 session
Files: `apps/api/models.py`, `engine/live/server.py` (narrate), `apps/api/main.py` (stream unchanged except
fields), `engine/apply/worker.py` (emit apply.start), `engine/shadow.py` (emit abstain), `engine/supervisor.py`
(problem/problem.clear on change), `engine/live/replay.py` (new: write `workspace/replays/<date>.jsonl`, scrubbed via
`export.py` privacy rules), `apps/web/lib/engine.ts` (`useEngine()` hook), `apps/web/lib/api.d.ts` (regen),
`tests/test_live_status.py`, `tests/test_replay.py` (new).
`useEngine()` returns `{ chips: Map<job, {stage, company, by}>, tray, trail, gear, shadow, parts: {name: up|cold} }`
built only from `subscribe()` events + one `/control/fleet` read at mount.
Accept:
- [ ] pytest green (299+ tests), new tests cover every `kind` mapping and that public replays contain no company/answer.
- [ ] Feeding tonight's events.jsonl through the hook (node test script) ends with the same submitted count as the ledger.
- [ ] `curl -N /api/stream` shows typed events during a live run.

### Phase 1: the living engine (home). Budget: 1-2 sessions
Files: `apps/web/app/page.tsx` (rewrite engine block), `apps/web/app/engine.css`, new
`apps/web/app/alive/{Engine.tsx,Chip.tsx,Cylinder.tsx,loop.ts}`. `backdrop.tsx` keeps its stream (shared).
- 5 cylinders by stage. A chip (company initial + name on hover) travels intake → cylinders in order. The cylinder
  fires (piston stroke + flash, 300 ms) as the chip passes.
- Outcomes: submitted → exhaust puff; parked → drops to tray; skipped → falls out with reason text fading 2 s.
- Idle: breath period = gear (N none, 1 = 4 s, 2 = 2.5 s, 3 = 1.5 s). Cold parts are grey for down containers.
- One rAF loop, ≤ 40 chips on screen (older ones collapse into a "+12" bundle), paused on `visibilitychange`.
- Reduced motion: chips jump between stations, no pistons, no breath.
Accept:
- [ ] Live run in the preview: chips flow with no reload for 10 min, CPU of the tab < 15% (DevTools perf sample).
- [ ] Stop `deploy-applier-1` → Apply cylinder goes cold + warning light within 30 s; start → warm again.
- [ ] 375 px: engine fits, no horizontal scroll; dark/light both readable; reduced-motion verified.

### Phase 2: Shadow co-driver. Budget: 1 session
Files: `apps/web/app/alive/{Seat.tsx,Captions.tsx}`, `engine.css`, `page.tsx`; backend only `/shadow` POST (exists).
- Selector **Off / Calls / Autopilot** on the seat → POST `/shadow`. The UI changes only when the `shadow.mode` event
  comes back (backend is the truth, no optimistic toggle).
- Handover on → autopilot: seat lights, the engine rim turns violet (`--shadow` token #a78bfa), and the caption
  "Shadow has the wheel" stays. Back to off: the rim cools, and the caption "You have the wheel".
- Parked chips curve to the seat; `shadow.answer` → back into Apply with caption + conf; `shadow.abstain` → tray,
  caption "Left this for you: <short reason>". CAPTCHA chips never go to the seat (drawn going straight to the tray).
- Seat badge: "level N · X% right on test" from `/shadow/brain` at mount + `shadow` train events.
Accept:
- [ ] Toggle in UI → `python -m engine shadow` in the pipeline container reports the same mode.
- [ ] 10 captions checked against ledger rows: same job, same by, same outcome.

### Phase 3: exhaust trail (receipts). Budget: 1 session
Files: `apps/web/app/alive/{Trail.tsx,ProofDrawer.tsx}`, `engine.css`.
- Each submit puff drifts up into a trail row (newest right). The trail is rebuilt from `/api/applications?today` on load.
- Click → drawer with resume, answers, proof screenshot (`/api/proof/{name}`, `/resume/{name}`). Public: role+lane only.
Accept:
- [ ] Every puff tonight opens the right proof; reload keeps the trail; public build shows no company names.

### Phase 5: four rooms as drawers + /docs. Budget: 1-2 sessions
Files: `apps/web/app/nav.tsx`, `layout.tsx`, new `apps/web/app/alive/Drawer.tsx`, new `apps/web/app/docs/page.tsx`
(+ `docs/*.md` content copied from the wiki, no new facts), `page.tsx`.
- Nav: **Drive · Your turn · Results · Garage**. Drawer slides over the engine (engine keeps running behind).
  - Your turn = Needs you + Desk. Results = Applications + Reach + Outreach.
  - Garage = Gearbox, Fact Bank, Memory graph, Shadow brain, Evals, Maintenance, MCP, Docs.
- Existing pages are rendered inside drawers as-is; their own routes still work.
- `/docs`: "Use REGEN" (start/stop, gears, Shadow modes, Desk, what NEEDS YOU means, FAQ) and "Build on REGEN"
  (containers table = §3, event contract = §4, API routes, MCP tools, Shadow brain, contributing).
- Remove `NEXT_PUBLIC_ALIVE` flag; the old home is deleted only after this phase passes.
Accept:
- [ ] Every old route still loads directly; each drawer opens/closes with keyboard (Esc), focus trapped.
- [ ] A non-technical read-through of /docs "Use REGEN" needs no other page to start a run.

### Phase 4: "While you were away" replay. Budget: 1 session
Files: `apps/web/app/alive/Replay.tsx`, `lib/engine.ts`, `apps/api/main.py` (`GET /api/replay?since=`).
- On open after > 30 min away (localStorage last-seen), play the gap compressed to ~30 s, then switch to live.
  A scrubber (play/pause, 1x/10x/60x) appears only during replay. Public site loops last night's scrubbed replay.
Accept:
- [ ] A 3 h run replays in 25-40 s and ends in the same state as live; skip button works.

### Phase 6: alive in the tab. Budget: ½ session
Files: `apps/web/app/alive/TabPulse.tsx`, `layout.tsx`.
- `document.title` = "REGEN · 3 sent · 2 yours" (only when changed); the favicon puffs 600 ms on submit.
Accept:
- [ ] Title updates from events within 2 s; no update when nothing changed.

## 5a. NEXT_STEPS work on the front end (merged 11-09 by the user)

The revamp starts once docs/NEXT_STEPS.md is finished, and it brings everything those steps built onto the screen:
nothing stays CLI-only after v2.0. The backend stays the truth: a control posts, and the UI changes only when the
event comes back. This table lists the work so far; when NEXT_STEPS closes, its remaining items are added here at
the Phase 0 triage.

| NEXT_STEPS item | Engine (built) | API (add if missing) | Event (Phase 0 kinds) | On screen (phase) |
|---|---|---|---|---|
| §1.1 Role Keywords per run | `engine keywords on\|off`, workspace/keywords.json | `GET/POST /control/keywords` (built 11-10) | `keywords` {on} | Drive panel toggle beside the gear lever, asked at ignition, "off" after a clean stop (Phase 1) |
| §1.2 + §2 interview rate + funnel | `engine report rate\|funnel` (Wilson intervals) | `GET /report/rate`, `GET /report/funnel` (built 11-10) | `outcome` (exists) | Rate beside every volume number ("446 sent · 0.2 per 100"); Results drawer funnel with splits and "not significant" said plainly (Phase 3 + 5) |
| §3 daily cap switch | `engine cap 0..4\|up\|down` = 15/25/50/100/150, profile/targeting.json | `GET/POST /control/cap` (built 11-10; CLI and API both emit `cap`) | `cap` {level, cap, today} | Cap dial next to the gearbox: level 0 at every start, "12 / 15 today" gauge, cap-reached state drawn as the engine idling, not as an error (Phase 1) |
| §3 targeting order | tier1 / sponsors first, then freshest; skip unsure fits (built 11-10: <5 covered terms or <40%) | `GET/POST /control/targeting` (built 11-10; emits `targeting`) | `gate.skip` detail "unsure fit" | Chips from tier1 / sponsors marked at intake; Garage > Targeting shows the settings (Phase 1 + 5) |
| §3 Role Keywords A/B | arm by URL hash (keywords.arm), `ab_arm` in the resume event, 150 per arm (built 11-10) | `GET /report/ab` (built 11-10: counts only until both arms are full) | `resume` {arm} | Results: two progress bars to 150, result hidden until both arms are full (Phase 5) |
| §4 outreach | `outreach 7` in the daily run, `outreach sent <company>` | `GET /outreach` (exists), `POST /outreach/sent` (built 11-10) | `outreach.sent` | Results > Outreach: drafts best first, Gmail compose link, a **Mark sent** button; funnel "applied + outreach" row (Phase 5) |
| §5 Shadow mode + never-answer list | `engine shadow calls\|autopilot\|off`, default calls | `/shadow` (exists) | `shadow.mode`, `shadow.abstain` | Phase 2 seat selector; never-answer questions drawn going to the tray with "left for you: work authorization" etc.; weekly precision on the seat badge |
| §6 quick start | `engine try resume` (no DB, nothing applied) | `POST /try` (public, rate-limited, nothing stored) | none | Public demo paste box: resume text in, top 10 roles + reasons out; /docs "Try it first" (Phase 5) |

API status 11-10: every row's route exists and is tested (tests/test_api.py round-trip + writes-off 403) except
`POST /try`, which is public and belongs to Phase 5 with its rate limit. openapi.json + apps/web/lib/api.d.ts
regenerated (56 paths); `npm run typecheck` clean. Phase 0 starts from this baseline.

Acceptance (added to the phases above): each control round-trips (UI → API → engine CLI reports the same value)
within one heartbeat; public build shows rates and arm counts but no company names; a V-bench row per control.

## 6. Quality bar: airtight (applies to every phase, no exceptions)

### Benchmarks (V-series, alongside the engine's B1-B10)
Harness: `scripts/bench_alive.py` (new in Phase 0, server side) + browser numbers taken in the preview with the
Performance panel. Results go to `docs/bench/alive.md` (one row per phase, date, commit). A phase that regresses a
V-number from the previous row does not ship.

| ID | What | Target | Measured by |
|---|---|---|---|
| V1 | Event → on screen latency | p95 ≤ 1.5 s | ledger ts vs DOM mutation (bench script + `performance.now`) |
| V2 | Tab CPU during a live run | ≤ 15% avg over 10 min | DevTools performance sample |
| V3 | Frame time with 40 chips | p95 ≤ 16.7 ms (60 fps) | rAF timing in `loop.ts` (dev-only counter) |
| V4 | Home JS added | ≤ 60 KB gzip vs v1.x home | `next build` output |
| V5 | Memory over 1 h live | growth ≤ 20 MB | heap snapshots start/end |
| V6 | Event coverage | 100% of a night's ledger kinds map to a `kind` (no unknown) | `bench_alive.py` over events.jsonl |
| V7 | Replay fidelity | replay end state == live end state | `tests/test_replay.py` |
| V8 | Public privacy | 0 company names, answers, emails, cities in public replay/feed | privacy scan + test |
| V9 | Container truth | part goes cold ≤ 30 s after stop, warm ≤ 30 s after start | stop/start applier in Phase 1 check |
| V10 | Accessibility | axe: 0 serious/critical; all controls keyboard-reachable; reduced motion honored | axe in preview + manual tab-through |

### Code standards (follow docs/CODING_STANDARDS.md, plus)
- Every new file opens with a header comment: what it is, why it exists, which plan phase added it.
- Every exported function/component has a doc comment: inputs, outputs, failure behavior.
- Types end to end: `api.d.ts` regenerated from `openapi.json` after any model change; no `any` in new web code.
- No silent catches: every `catch` logs or surfaces a visible state (part goes cold, or a caption explains it).
- The UI never invents state. Everything drawn comes from an event or an API read, and controls wait for the backend's event.

### Leaks and loopholes (security/privacy checklist, run every phase)
- No new write endpoints. UI controls reuse existing ones (`/control/gearbox`, `/shadow`) and their existing guards.
- `/api/replay` is read-only. The public build serves only the scrubbed file (V8), never raw events.
- The SSE stays bound to 127.0.0.1 locally. The public build opens no stream (lib/stream.ts already enforces this).
- No secrets, emails, names or cities in commits: the privacy scan (pre-commit) must pass with no override.
- Event text is rendered as text, never `innerHTML` (job/company strings come from the internet).
- Resource leaks: every `subscribe`, listener, timer and rAF is cleaned up on unmount (checked by V5).

## 7. Order, checks, rollback
Order: Track A 0 → 1 → 2 → 3 → 5 → 4 → 6 (about 7-9 sessions; v2.0 ships after 5), then Track B 7 → 12 in
the order the user picks at triage. After every phase:
1. `pytest` + `npm run typecheck` in apps/web.
2. `docker compose -f deploy/bank.compose.yml build web api`, then recreate **web + api only** (never the desk with
   filled tabs; appliers only at claimed 0).
3. Preview check: desktop, 375 px, dark, reduced motion; console clean; screenshot to the user.
4. Privacy scan passes; local commit; HANDOFF.md + wiki page "Alive engine" updated.
Rollback: `NEXT_PUBLIC_ALIVE=0` (until Phase 5) or `git revert` the phase commit.

## 8. Idea inbox (feedback model, step 1)
| Date | Idea | Triage |
|---|---|---|
| 11-07 | Phone push, sound pack, 3D engine, inner pages, Shadow L2+ visuals, weekly highlights | accepted as Track B phases 7-12 (user, 11-07) |
| 11-09 | Cap switch on the front end; all NEXT_STEPS changes part of the revamp | merged into Track A as §5a (user, 11-09) |
