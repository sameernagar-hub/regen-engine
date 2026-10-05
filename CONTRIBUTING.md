# Contributing to REGEN

Thanks for helping build an honest job engine. Three rules come before everything else:

1. **No real personal data, ever.** Use the fictional persona in `tests/fixtures/presets.json` (Jane Doe) and `profile.example/`. Company names in tests should be fictional (Acme, Globex, Initech, Hooli, Umbrella, Vandelay…).
2. **No fabrication.** Anything that writes resumes, answers or messages must draw only from the user's Fact Bank and presets, and must keep the audit trail (fact ids, question → answer).
3. **No bypassing.** No CAPTCHA solving, no bot-detection evasion, no auto-created accounts, discovery-only on LinkedIn/Indeed/Handshake.

## Setup
```bash
git clone https://github.com/sameernagar-hub/regen-engine && cd regen-engine
pip install -r requirements.txt pytest && playwright install chromium
python -m pytest -q
```

## Before you open a PR
- [ ] `python -m pytest -q` passes
- [ ] `python scripts/privacy_scan.py` reports `privacy check: clean`
- [ ] Your commits use your GitHub **noreply** email (Settings → Emails → "Keep my email addresses private")
- [ ] `CHANGELOG.md` has an entry: what changed, why, how to verify
- [ ] New behavior has a test

CI runs the same privacy gate and tests; `main` only accepts merges that pass both.

## Good first contributions
- **ATS adapters:** Lever and Workable apply (discovery already exists in `engine/discovery/ats.py`)
- **Discovery sources:** another public ATS API or machine-readable job list
- **Live view:** the v0.7 Next.js + TypeScript version, and the GPU "engine room" ([docs/FRONTEND.md](docs/FRONTEND.md))
- **Lean engine:** conditional requests (ETag / Last-Modified) to skip unchanged boards
