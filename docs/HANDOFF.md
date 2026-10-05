# Handoff: where the engine stands (v0.3, 2026-10-05)

## What works end to end
- `python -m engine scan [days]`: scans the Greenhouse boards in `workspace/boards.txt` in parallel, filters by `profile/domains.json`, and dedupes against `workspace/ids.txt` (appended automatically after each submit).
- `python -m engine feed [days]`: SimplifyJobs new-grad feed, tagged by ATS. Workday and iCIMS links need an account the user creates.
- `python -m engine batch <name> <id,...>`: fetches each job description, routes it to a lane from `profile/lanes.json`, builds a Fact-Bank-validated one-page PDF, and flags human questions.
- `python -m engine apply batches/<name>.json [--dry]`: Greenhouse is reliable. At the **email security code** step it waits for `workspace/code.txt`. The operator (an agent with Gmail access, or you) reads `from:greenhouse security code` and writes the code there.
- `python -m engine status`: latest status per job from `workspace/events.jsonl`.
- First run: 7 applications submitted (the local `workspace/tracker.md` has the details).

## Known bugs / next fixes (in priority order)
1. **ACK matching**: arbitration and "I have read" selects use option wording that `__ACK__` misses. Log the option texts and widen `ACK` in `engine/apply/runner.py`.
2. **Greenhouse education block**: Degree, Discipline and School are react-selects inside `.education`, so the fields aren't scanned.
3. **Ashby adapter**: radio and combobox state doesn't stick on some boards. Try `page.get_by_label(text).check()` and a keyboard-only combobox, and verify state before submitting.
4. **Gmail code loop**: automate it (Gmail API/OAuth) so the runner fetches codes itself. This is also the start of the outcome classifier (v0.6).
5. **Memory ingesters (v0.4)**: `fact_bank.json` + `events.jsonl` → Neo4j/pgvector using `engine/memory/schema.cypher`.
6. **Scheduler**: run `scan` every 15 minutes and auto-build batches from a fit score.

## How to resume
```bash
python -m engine scan 2
python -m engine batch b3 <id,id,...>
python -m engine apply batches/b3.json --dry   # check workspace/proof/
python -m engine apply batches/b3.json         # submit; feed email codes into workspace/code.txt
python -m engine status
```
