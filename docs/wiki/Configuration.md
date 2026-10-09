# Configuration

Everything personal lives in `profile/` (git-ignored; start from `profile.example/`). Runtime state lives in
`workspace/` (git-ignored). Secrets live in `.env` (git-ignored).

## Profile files

| File | Purpose |
|---|---|
| `fact_bank.json` | the only source of resume content: facts, roles, projects, skills, education, overlaps |
| `lanes.json` | resume lanes and routing rules |
| `domains.json` | include/exclude titles, excluded employers, location rules |
| `presets.json` | every legal, status and preference answer (authorization, sponsorship, citizenship, EEO decline, salary policy, relocation, start date, time zone, visa-type spellings, ...). Entries Claude drafted on your instruction are listed in `_drafted_by_claude_*` for review |
| `answers.json` | answers you approved once, reused on every form (`pattern`, `answer`, `source`) |

## Environment variables

| Variable | Default | Effect |
|---|---|---|
| `REGEN_TABS` | 3 | tabs per applier (round-robin) |
| `REGEN_PW_PROFILE` | `pw-profile` | Chromium profile dir per applier |
| `REGEN_MAX_PER_DAY` | 25 | airbag: daily submission cap |
| `REGEN_SKIP_ATS` | – | comma list of ATSs the pipeline won't select (e.g. `workable`) |
| `REGEN_DRAFT` | 1 | draft open-ended answers from the Fact Bank |
| `REGEN_AUTOFILL` | 1 | yes/no policy for non-status questions |
| `REGEN_WEBHOOK` | – | watcher announcements |
| `REGEN_SMTP_USER`, `REGEN_SMTP_APP_PASSWORD`, `REGEN_SMTP_HOST/PORT`, `REGEN_IMAP_HOST`, `REGEN_ALERT_TO` | – | SOS email, IMAP inbox and `codes --watch` |
| `REGEN_MODE` | local | `public` = anonymized feed only |
| `REGEN_API_WRITE` | 0 | allow `POST /api/answers` (localhost) |
| `REGEN_MCP_WRITE` | 0 | allow MCP pipeline/code tools |
| `REGEN_DATABASE_URL` | – | Postgres mirror |
| `REGEN_WORKSPACE`, `REGEN_PROFILE`, `REGEN_FACT_BANK`, `REGEN_PRESETS` | repo paths | relocate data (tests use `profile.example/`) |

## CLI reference

`scan · newgrad · alerts · feed · bigtech · boards · watch · batch · tailor · inspect · apply · codes · status ·
inbox · learn · report · run · graph · live · site · mcp · sos-test`. Run `python -m engine` for the one-line help
of each.

Related: [Running the engine](Running.md) · [Truthfulness and safety](Truthfulness-and-Safety.md)
