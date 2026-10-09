# Testing and evidence

Every number in the docs can be reproduced, and every behaviour that matters has a test.

## The suites (`tests/`)
| File | What it proves |
|---|---|
| `test_core.py` | discovery filters, board harvesting, fit gate, tailoring and validation, answer rules, option picking |
| `test_v08.py` | scheduler (overlap, preemption, failure isolation, quantum maths), drafts (only open questions, only Fact Bank text, honest closings), event log (3 processes × 200 large lines never tear; incremental, tolerant reads), the long-term sponsorship rule and its airbag, no control characters in the rules, experience and "select all" answers, code matching |
| `test_api.py` | every API endpoint over a seeded log; the answer write path is off by default, localhost only, refuses legal/EEO/sensitive questions, replaces instead of duplicating, re-queues the job |
| `test_forms.py` | the **real filler in headless Chromium** against local look-alikes of Greenhouse, Ashby and Lever: drafted "why" answer from the Fact Bank, sponsorship from presets, EEO declined, CSS-only required field caught, follow-up questions, proof screenshot on disk, dry runs never submit |

Tests use a fictional persona (`tests/fixtures/presets.json`, `profile.example/`) and a throwaway workspace; they never
read real data. The form tests intercept requests to the ATS hosts and answer with the fixture page, so nothing
leaves the machine.

## Coverage
```bash
python -m pytest -q --cov=engine --cov=apps/api --cov-report=term-missing
```
CI runs the same command on every pull request (the form tests are skipped there if Chromium isn't installed).

## Benchmarks
| Script | Claim it checks |
|---|---|
| `scripts/bench_scheduler.py [jobs] [tabs] [seed]` | round-robin speed-up and browser utilization (deterministic clock) |
| `scripts/bench_tailor.py <old tailor.py>` | the new tailoring returns identical output on every saved JD, and how much faster |

## Evidence in production
- `python -m engine report`: only submissions whose proof screenshot exists.
- `schedule` events: real wall time, active time and switches for each run.
- `workspace/drafts_review.md`: every drafted answer with its fact ids.


Related: [Home](Home.md) · [Architecture](Architecture.md) · [Discovery](Discovery.md) · [Fit gate](Fit-Gate.md) · [Tailoring](Tailoring.md) · [Apply engine](Apply-Engine.md) · [Email codes](Email-Codes.md) · [Outcomes](Outcomes-and-Learning.md) · [Platform](Platform.md) · [Metrics](Metrics.md)
