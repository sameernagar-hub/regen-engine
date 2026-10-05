# Changelog

Every change to the engine, newest first. Each entry says **what** changed, **why**, and **how to verify** it,
so a reviewer can check the work without reading the whole diff.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow the README roadmap.

## [0.4.0] - 2026-10-05 · "More sources, fewer stalls"

### Added
- **Multi-ATS discovery** (`engine/discovery/ats.py`, `scan.py`): one scanner for **Greenhouse, Ashby, Lever and Workable** public board APIs, normalized to a single job record (`ats, token, id, company, title, location, posted, url`). About 2,300 boards (110k postings) scan in about 45 s, up from 345 Greenhouse boards.
  *Verify:* `python -m engine scan 1` prints `scanned N boards, M postings`.
- **Board registry** `workspace/boards.json`, migrated automatically from the old `boards.txt`. `python -m engine boards harvest` grows it from the SimplifyJobs JSON lists and the READMEs of speedyapply, vanshb03, SimplifyJobs and ReaVNaiL. Boards that 404 are recorded under `dead`.
- **`watch` mode** (`engine/discovery/watch.py`): polls every board on an interval (default 10 min) and announces only postings that didn't exist on the previous poll, with minutes-since-publish. Writes `workspace/new.jsonl`, logs `discovered` events, and POSTs to `REGEN_WEBHOOK` (Slack, Discord, n8n, Zapier) if it's set. The first poll only seeds `seen.json`, so it never floods.
- **newgrad-jobs.com source** (`engine/discovery/newgrad.py`, `airtable.py`): reads the site's public Airtable views (SWE, AI/ML, Data Eng; about 150 new rows a day). Its links hide the employer's posting behind jobright.ai, so each row is resolved to the company's **own** Greenhouse/Ashby/Lever board by company slug and title match. Resolved boards join the registry, so later scans watch them directly. Unresolved rows go to `workspace/leads.json`.
- **JD fit gate** (`engine/tailoring/tailor.py: fit`): before a resume is built, the job description is checked for citizenship/ITAR, clearance/polygraph, "no sponsorship", grad windows you're outside of, and years required above your level. Blocked jobs are logged as `SKIPPED` with the reason and never re-queued. `--force` overrides.
- **Per-job tailoring, still Fact-Bank-only** (`tailor.tailor`): keeps the lane's shape (same roles, bullet counts and project count) but picks and orders bullets, projects and skill lines by how many of the job's technologies they mention. Candidates are only the bank's own facts for that role, and `validate()` still gates the result. Each build prints a coverage line ("resume covers 15/15 JD terms").
- **Transparency log:** every `resume` event records the exact fact ids, projects, skills and lane used, so every claim on every resume traces to a Fact Bank entry.
- **`inspect` command** (`engine/apply/inspect_form.py`): headless read of any Greenhouse or Ashby form. Lists each field, whether it's required, its options, and the answer the engine would give, or `UNKNOWN`. Use it to see which questions a job needs before applying.
- **Answer bank** `profile/answers.json` (optional): answers you approve once and that are reused on every form (`[{pattern, answer, source}]`). Checked after per-job `extra`, before the built-in rules.
- **Data lane** support: routing rule for data-engineering titles (lane lives in your private `profile/lanes.json`).
- **Tests** (`tests/`, `python -m pytest -q`): filters, harvesting, fit gate, Fact-Bank validation of tailored specs, answer rules and option matching. They run against `profile.example/` and a temp workspace, never your real data.

### Changed
- `batch` is ATS-agnostic (Greenhouse, Ashby, Lever, Workable job descriptions) and records `ats` and `lane` per job.
- Domain filter moved to `engine/discovery/filters.py` and is shared by every source. It adds a real US-location test (state codes, US cities, non-US country list), excluded employers (defense/ITAR, since you need sponsorship), and more excluded levels and titles (VP, architect, polygraph, mobile, 2027, research scientist...).
- `engine/discovery/greenhouse.py` is now a compatibility shim over the new modules (old imports keep working).
- `profile.example/domains.json` now mirrors the engine defaults. The old example silently weakened the filter.
- Greenhouse selects open once and choose from the full option list, and only fall back to typed search for long or async lists. EEO-heavy forms went from minutes per question to seconds.
- Ashby comboboxes (e.g. location autocomplete) choose the best matching option instead of requiring exact text.

### Fixed
- **Runner stalls:** every Playwright action now times out (15 s, 45 s for navigation) instead of hanging a whole batch. Each field is logged as it's filled.
- **Double-apply guard:** `apply` skips any job whose URL is already `SUBMITTED` in the event log, so re-running a batch is safe.
- **Wrong answer:** the disability question ("...limits one or more of your *major* life activities") was answered "Computer Science" by the field-of-study rule. EEO and demographic questions are now matched first, and `major` is word-bounded.
- **Wrong answer risk:** a Greenhouse select with no matching option used to click the first of up to 3 filtered options. Now only a single remaining option that contains the searched text is accepted. Otherwise the job goes to the human queue.
- **ACK matching:** "I have read and agree", "I understand", "Acknowledged"... are recognized, and negatives ("I do not agree", "Not now") are never picked.
- **Over-broad rules:** "source" no longer catches "Open source community"; "race" no longer catches "tracing"; "community" no longer catches unrelated questions.
- New provable answers: "based in the U.S.", "earliest start", "preferred location", "do you have a college degree", "currently enrolled", "highest level of education". `type=url` inputs (Ashby LinkedIn) are filled.
- Years-of-experience parser: "5 to 15+ years" means 5+ (it used to read 15+), and en-dash ranges ("4–7 years") parse correctly.
- Grad-window check no longer blocks "degree **by** June 2027", which a 2026 graduate already meets.

### Policy (unchanged, now enforced in code)
- **Arbitration** agreements are never answered by default. They need a per-job `extra` (your approval for that company).
- Jobs on ATSs without an adapter (Lever, Workable) get a tailored resume and a `NEEDS YOU` entry. They're never pushed through the wrong filler.

## [0.3.0] - 2026-10-05
- Engine package, CLI (`scan / feed / batch / tailor / apply / status`), Greenhouse + Ashby apply, Fact Bank validator, event log, memory stack definition, architecture docs. First real run: 7 applications.
