# Handoff: v0.8 shipped, v0.9 next (2026-10-08)

Every change, with how to verify it: **[CHANGELOG.md](../CHANGELOG.md)**. Ideas and design notes: **[the wiki](wiki/Home.md)**.

## State
- `main` = v0.8 (round-robin applying, parallel appliers, `engine run`, autofill from the Fact Bank, salary from the
  posted range, answer from the page, locked event log, faster tailoring, browser tests). CI runs on every push;
  admin pushes to `main` no longer wait for it. The local pre-push privacy hook still blocks leaks.
- No schedules: the engine runs only when started.
- First day of v0.8 in use: 9 verified submissions on 10-07.

## Run a day
```bash
python -m engine run --days 1 --max 30 --appliers 2 --tabs 3   # scan, pick, resumes, apply, report
python -m engine feed 3 --queue                                # GitHub new-grad lists into the queue
python -m engine report                                        # verified submissions only
```
Greenhouse email codes: run `engine/discovery/gmail_codes.js` in a Gmail tab (open a fresh tab if Gmail stalls),
then `python -m engine codes '<json>'`. Alert emails: `engine/discovery/gmail_alerts.js`, save the article text to
`workspace/alerts/<date>.txt`, `python -m engine alerts <file>`.

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
