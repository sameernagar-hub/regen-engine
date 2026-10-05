# The live engine: frontend concept and research

> Not a dashboard. A window into a workforce that's working for you right now.

## The idea
Dashboards answer "what are the numbers?" with rows, columns and charts. The engine's frontend should answer
**"what is it doing for me right now, and does it need me?"**, the way you'd glance at a workshop through a window.

One screen, no navigation. Five stations on a quiet line, named as verbs:

**listening → judging → writing → applying → hearing back**

- **Listening:** a faint field of points around the first station, one per company board being watched (about 2,300). A soft ring pulses out each time the watcher finishes a pass.
- **Work moves as light.** Every real event (a job spotted, a job let go, a resume written, an application sent, a reply received) is a point that travels between stations. Jobs that are let go sink away quietly instead of being listed.
- **One sentence at a time.** At the bottom, the engine narrates in plain English: *"Spotted Nuro: New Grad Software Engineer, 3 min after it went live."* Older lines fade. No jargon, no ids.
- **Embers.** Each verified application (confirmation screenshot on disk) leaves a permanent gold ember above *applying*. The only big number on screen is that count, and it's always evidence-backed.
- **The human.** A single amber line, "3 things are waiting on you", opens a short list of what needs you now, computed from each job's latest status (never stale history).
- **Alarms are rare and red:** an airbag stop, a scam email. Wins are gold: an interview, an OA, an offer.

### Rules that keep it from turning into a dashboard
1. No tables, cards, tabs, sidebars or charts. If something needs a table, it belongs in a file (`report`, `outcomes.md`).
2. Every element maps to something the engine actually did. No decorative fake activity: the replay on load is real recent events.
3. Words over numbers. One number, and it's proof-backed.
4. Calm by default. Motion only when work happens; `prefers-reduced-motion` turns travel off and keeps the words.
5. Truthful copy. The narrator never claims proof unless the file exists, and never invents counts.

## How it works (v0.6 prototype, shipped)
```
events.jsonl ──tail──> engine/live/server.py ──narrate()──> SSE /stream ──> engine/live/index.html (Canvas 2D)
   (append-only)        stdlib, read-only, 127.0.0.1        one sentence per event      no build, no CDN, no tracking
```
- `python -m engine live` opens http://127.0.0.1:7777, or it runs always-on as the `live` service in `deploy/watcher.compose.yml` (read-only workspace mount, published on 127.0.0.1 only, 128 MB).
- On connect, the server sends a snapshot from the evidence on disk (verified count, what's waiting, boards, last poll), replays the last 40 events quickly so the page opens alive, then streams new events.
- Zero dependencies: Python standard library plus one HTML file with a strict CSP. Nothing leaves your machine.

## Roadmap for the frontend
| Version | What | Notes |
|---|---|---|
| **v0.6** ✅ | Live view prototype: stations, light, narrator, embers, "waiting on you" | Local + Docker |
| v0.6.x | **"A day in 60 seconds"** replay (`/replay?day=…`), and click an ember to see that application's proof and the exact facts used | Transparency as a feature |
| v0.7 | **The workforce:** each lane (backend, platform, AI, data…) becomes a distinct worker light with its own rhythm; replies flow back to the worker that earned them, so you *see* which lane gets interviews | Driven by `learn` |
| v0.7 | **Answer the human from the page:** the "waiting on you" items accept a reply that goes into `profile/answers.json` (with the source recorded), then the job re-runs | Write path guarded by the same airbags |
| v0.8 | **Phone:** view the same page securely from your phone, plus push alerts for SOS / interviews | see free services below |
| v0.8 | **Public demo:** an anonymized replay ("a fintech in NYC", no names) on GitHub Pages so people can see the engine work without seeing your data | Branding moment |
| later | Optional sound (Web Audio: a soft tone per verified application, opt-in), 3D "engine room" variant | Only if it stays calm |

## Free services that fit (local-first stays the rule)
| Need | Option | Why it fits | Cost |
|---|---|---|---|
| See the live view from your phone | **Tailscale** (private network between your devices) | Nothing public; end-to-end encrypted; works with the existing 127.0.0.1 service via `tailscale serve` | Free personal plan |
| Same, with no app on the phone | **Cloudflare Tunnel** + Cloudflare Access (email login) | No open ports; access limited to your email | Free tier |
| Push alerts (SOS, interview, OA) | **ntfy** self-hosted as a Docker service | Open source, runs next to the watcher, phone app subscribes; no third party sees content | Free |
| Public demo page | **GitHub Pages** (static, anonymized replay JSON) | Already where the repo lives | Free |
| Shareable private snapshot | **claude.ai Artifacts** (private by default) | Publish a one-off anonymized replay page for a reviewer | Included |
| Hosted backend if ever wanted | **InsForge "AIPent"** project (already provisioned for this workspace) | Postgres + realtime + storage if a multi-user version is built; opt-in, never required | Free tier |
| Visual upgrades (optional) | three.js / p5.js (MIT), Rive (free tier) for worker animations; self-hosted variable fonts (OFL, e.g. Fraunces + Inter) | Bundled locally, no CDN calls | Free |

**Recommendation:** next build the click-an-ember proof view and the 60-second day replay (pure local, highest "wow per line of code"), then ntfy + Tailscale for phone. Hold off on 3D until the 2D view's language feels finished.
