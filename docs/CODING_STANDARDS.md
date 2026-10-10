# REGEN coding standards (v1 track)

These rules apply to every change, from a one-line regex to a new subsystem. Reviews check them in this order.

## 1. Non-negotiables (a PR that breaks one is closed, not fixed)
1. **Truth.** Generated text (resumes, answers, outreach) may only reword Fact Bank entries and presets. Every
   generated artifact logs its sources (fact ids, question → answer). No "reasonable guesses" about the user.
2. **Personal answers live in presets, never in code.** Yes/No, status, legal, salary and demographic answers are
   preset keys (`P.get("...")`). `tests/test_core.py::test_no_personal_defaults_in_code` enforces it.
3. **Trust before data.** Personal data is only typed into forms on an ATS host that passed
   `engine/discovery/trust.py`. `--force` never overrides the trust gate.
4. **No bypassing.** No CAPTCHA solving, bot-detection evasion, account creation or credential entry. A wall
   ends the attempt and goes to the user's assist list.
5. **Zero cost, local first.** No paid API keys. Intelligence comes from the user's own AI client through MCP.
   Network calls are minimized (cache, skip dead boards, one fetch per posting).
6. **Privacy gate clean.** `python scripts/privacy_scan.py` must pass: no personal data, no company names from the
   user's applications in code, docs, comments or tests. Use fictional names (Acme, Globex, ExampleCo).

## 2. Python
- Python 3.12+, standard library first. A new dependency needs a reason in the PR (what it replaces, its size).
- **Every public function has a docstring** that states what it returns, what it reads/writes, and its complexity
  when it loops over jobs, events or boards (`O(E)` over the event log, etc.). Private helpers get one line.
- Module docstring at the top of every file: purpose, the CLI command that uses it, data it touches.
- Names say what a thing is (`blocked_companies`, not `bc`). Regex constants are UPPER_CASE and compiled once.
- Pure functions for decisions (fit gate, trust gate, answer rules) so they are unit-testable without a browser.
- Side effects go through `engine.feedback.events.record(...)` so every decision is in the append-only log.
- No bare `except:`. Catch the narrowest exception and say in a comment why it is safe to continue.
- Comments explain *why* (often the incident that caused the rule: "10-09: a slug without spaces dodged the
  exclusion"), never restate the code. Dates in ISO form.
- Formatting: 4 spaces, lines ≤ 120 chars, f-strings, no trailing whitespace. Keep functions under ~60 lines; split
  when a function has more than one reason to change.
- Edit scripts on Windows: write them as files (Git Bash heredocs turn `\b` into a backspace; the control-char test
  catches it).

## 3. TypeScript / web (apps/web)
- Next.js App Router, React 19, TypeScript strict. `npx tsc --noEmit` must be clean.
- Types for API data come from `apps/api/openapi.json` (`npm run gen:api`), not hand-written copies.
- Every page starts with a comment: what it shows, where its data comes from, what it can change.
- Accessibility is part of done: keyboard reachable, visible focus, `aria-*` on custom controls, `prefers-reduced-motion`
  respected, contrast checked, works at 360 px wide.
- Motion maps to real events (a job submitted, a stage processing). No decorative loops that hide state.
- Writes from the UI go through API endpoints guarded by `REGEN_API_WRITE=1` and a localhost check.

## 4. Tests and evidence
- New behavior ships with a test in `tests/` that would have failed before the change. Incidents become regression
  tests (one per rejection cause or mis-submit).
- `python -m pytest -q` green before every push. Benchmarks live in `scripts/bench_*.py`; claims about speed in docs
  cite a benchmark run.
- UI changes include a screenshot or recording in the PR.

## 5. Commits, branches, releases
- One logical change per commit; subject in the imperative, ≤ 100 chars, body says why and how to verify.
- `main` moves only by fast-forward from a CI-green branch (merging on GitHub stamps a personal email).
- Every user-visible change: `CHANGELOG.md` entry (what / why / verify) and the matching wiki page updated in the same
  push. Version bumps follow SemVer; v1.0 freezes the CLI, the event schema and the MCP tool names.

## 6. Review checklist
- [ ] Non-negotiables 1–6 hold
- [ ] Docstrings + module docstring present; complexity noted for loops over data
- [ ] Test added; pytest, tsc and privacy scan clean
- [ ] CHANGELOG + wiki updated
