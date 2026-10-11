# Contributing to REGEN

Thanks for helping build an honest job engine. Three rules come before everything else:

1. **No real personal data, ever.** Use the fictional persona in `tests/fixtures/presets.json` (Jane Doe) and `profile.example/`. Company names in tests should be fictional (Acme, Globex, Initech, Hooli, Umbrella, Vandelay…).
2. **No fabrication.** Anything that writes resumes, answers or messages must draw only from the user's Fact Bank and presets, and must keep the audit trail (fact ids, question → answer).
3. **No bypassing.** No CAPTCHA solving, no bot-detection evasion, no auto-created accounts, discovery-only on LinkedIn/Indeed/Handshake.

## Coding standards
Read [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md) before writing code: non-negotiables (truth, presets-not-code,
trust before data, no bypassing, zero cost, privacy gate), Python and TypeScript style, docstrings with complexity,
tests-as-evidence, and the release rules toward v1.0.

## Setup
```bash
git clone https://github.com/sameernagar-hub/regen-engine && cd regen-engine
pip install -r requirements.txt pytest && playwright install chromium
python -m pytest -q
python scripts/bench_system.py        # system benchmarks B1-B4 (see docs/wiki/Benchmarks.md)
```
To run the whole engine in Docker, see the Quick start in the README (`deploy/bank.compose.yml`).

## Before you open a PR
- [ ] `python -m pytest -q` passes
- [ ] `python scripts/privacy_scan.py` reports `privacy check: clean`
- [ ] Your commits use your GitHub **noreply** email (Settings → Emails → "Keep my email addresses private")
- [ ] `CHANGELOG.md` has an entry: what changed, why, how to verify
- [ ] New behavior has a test; a new failure mode also gets a benchmark in `scripts/bench_system.py`
- [ ] Public functions have docstrings (what, side effects, complexity) — see the standards
- [ ] `npx tsc --noEmit` clean in `apps/web` for UI changes; screenshot attached

CI runs the same privacy gate and tests; `main` only accepts merges that pass both.

## Good first contributions
- **ATS adapters:** Workday and iCIMS apply (account-based portals; must stop for the human at any login or captcha)
- **Discovery sources:** SmartRecruiters public postings API, or another machine-readable job list
- **Missing answers:** run `scripts/bench_system.py`; B2 prints questions no rule answers yet. Add a rule plus a test
  (never for legal, EEO or sponsorship questions)
- **Benchmarks:** B5 submissions per hour by worker count, B6 email-code latency, B7 fit-gate precision
  ([docs/wiki/Benchmarks.md](docs/wiki/Benchmarks.md))
- **Control room:** a supervisor view of the containers (health, inbox, claimed and done counts) in `apps/web`
- **Lean engine:** conditional requests (ETag / Last-Modified) to skip unchanged boards
