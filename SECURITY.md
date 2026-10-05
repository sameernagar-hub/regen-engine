# Security & privacy

REGEN works with the most personal data a person has: identity, work history, immigration and eligibility answers, and inbox. The rule is simple: **personal data never enters this repository**, and that's enforced by code, not good intentions.

## What stays local (git-ignored, never committed)
- `profile/`: your Fact Bank, presets (legal and eligibility answers), lanes, answer bank, private terms, and the privacy key
- `workspace/`: queue, resumes, proof screenshots, event log, inbox exports, browser session
- `.env`: SMTP/IMAP app passwords and webhooks

The engine has **no hardcoded personal answers**. Every eligibility or status answer (work authorization, sponsorship, relocation, degree, start date…) comes from your git-ignored `profile/presets.json`, and an unset preset sends the question to you instead of guessing.

## The privacy gate (runs on every PR and every push to `main`, admins included)
`scripts/privacy_scan.py --ci` fails the build on any of:
1. **PII patterns**: email addresses (except `example.com` / GitHub noreply), phone numbers (except fictional 555 numbers), SSNs, API keys and tokens, private keys.
2. **Forbidden paths**: anything under `profile/`, `workspace/` (except `.gitkeep`), `.env`, PDFs and DOCX files.
3. **Commit identity**: every author and committer email of new commits must be a GitHub noreply address (commits that predate the gate are listed by SHA in `.privacy/accepted_history.txt`; no new exceptions).
4. **Private-term fingerprints**: `.privacy/denylist.json` holds HMAC-SHA256 fingerprints of the maintainer's private terms (name, contacts, employers, schools, companies applied to…). CI fingerprints every word sequence in the repo with the `PRIVACY_KEY` secret and compares. Without the key, the fingerprints reveal nothing, not even guessable company names.
5. **Public site**: `site/replay.json` must contain no status-revealing wording; the build itself refuses to publish if any company name from the event log would appear.

`main` is protected: merges require the gate and the tests to pass, and the protection applies to administrators too.

### Locally
```bash
python scripts/privacy_scan.py --install-hook   # runs the check before every git push
python scripts/privacy_scan.py --history        # on demand
python scripts/privacy_scan.py --update-denylist && gh secret set PRIVACY_KEY < profile/.privacy_key   # after adding private terms
```

## Public site
The public demo (`site/`, built by `python -m engine site`) replays recent activity **anonymized**:
- **Kept:** role titles, stages, outcome types, generic skip categories (eligibility, seniority, graduation window), counts.
- **Removed:** company names, anything waiting on the candidate, answers, URLs, emails, files.

The local live view (`python -m engine live`) is bound to `127.0.0.1` and is read-only.

## Reporting a vulnerability or a leak
Please **don't open a public issue**. Use GitHub's private vulnerability reporting (Security → Report a vulnerability) on this repository.
