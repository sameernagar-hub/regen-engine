# Maintenance (the oil change)

REGEN is drawn as an engine because a job search runs like one. This page says what the maintenance part means and how it works.

## What builds up
Every application leaves something behind. Left alone, these slow the engine and let stale jobs back into the queue:

| Leftover | Limit | Cleared by |
|---|---|---|
| Expired files: tailored resumes (3 d), job-description cache, logs, old batches, proofs past 90 d | 400 MB | **Clear expired files**: deleted; proof screenshots are shrunk in place, never lost |
| Verification-code mail (2 d+) and job-alert mail (7 d+) | 300 mails | **Tidy the inbox**: moved to Gmail's Bin (undoable for 30 days); starred mail is never touched |
| Idle Docker build cache, dangling images, an applier whose browser grew | 6 GB / 1.4 GB | **Free machine space**: cache pruned least-recently-used first down to 2 GB; that applier restarts between applications |
| Postings older than 45 days, or already applied to / ruled out | 300 | **Refresh the job queue**: they leave `queue.json` |

**Health (oil life)** = 100 minus the larger of: time since the last clean-up (as a share of 24 h), and the fullest leftover (as a share of its limit).

## When it runs
- The supervisor inspects every 5 minutes (Docker and the mailbox at most every 30) and cleans when health reaches 10%.
- **Clean up now** on `/oilchange` asks for one; the supervisor starts it once its current inspection ends.
- A clean-up that cannot lift health above 10% (for example, cache from today's builds that is still in use) is not retried on schedule for 24 h. Asking still works.

## Watching it
From the click until the run ends, the page polls every second. Every step the server reports, including one that finished between two polls, plays in order for at least 2.8 s: files drain from the tank, the inbox filter swaps, the cache runs to the Docker drum, live jobs pour back in, and the gauge reads the new health.

## Trust
REGEN's promise is that every action has evidence. Maintenance keeps it: each clean-up is written to the event log and the page's history with every stage's count and MB freed, proof screenshots are shrunk but never deleted, mail goes to Bin (undoable), and anything outside REGEN's own stack is reported, never removed.

## Never touched
`profile/` (Fact Bank, presets, answers), `events.jsonl` (the application log and its proof), named volumes, other projects' containers, images in use, starred or recent mail. Gmail's All Mail is never expunged.

## Reading the rest of the engine
| Part | Means |
|---|---|
| Cylinders and pistons | the seven working views; a firing piston is that view doing work |
| Fuel | the Fact Bank: every resume line burns a fact you can prove |
| Gears | speed: how many appliers run and how often boards are scanned |
| Clutch | whether rejection lessons may change which jobs are applied to |
| Wiring | the memory graph: you, applications, companies, facts, outcomes |
| MCP cord | where your AI assistant plugs in |

Code: `engine/oilchange.py`, `apps/web/app/oilchange/`. Tests: `tests/test_v12_oilchange.py`.
