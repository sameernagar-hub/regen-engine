# Evidence

Every public claim about REGEN, and how to check it yourself. Personal data never appears here; the commands
read your own ledger.

| Claim | Evidence | Check it |
|---|---|---|
| 118 verified applications to date | an `application` event with status `SUBMITTED` and a proof screenshot of the confirmation page | `python -m engine report` (in the bank: `docker compose -f deploy/bank.compose.yml run --rm --no-deps --entrypoint python pipeline -m engine report`) |
| 46 verified on 2026-10-10 | same, filtered by day | `... -m engine report 2026-10-10` |
| Resumes contain only your facts | the validator rejects lines outside the Fact Bank before rendering | `tests/test_compose.py`, `resume.validate` |
| Resumes cover the JD terms you have | `resume` events carry `coverage` and `ats.score` | B4 in [Benchmarks](Benchmarks) |
| Legal questions are never inferred | `LEGAL_OR_SENSITIVE` / `STATUS_Q` route them to you | `test_possess_years_questions`, B2 `legal_user_only` |
| Each batch is applied once | exclusive-lock claims | B3, `test_worker_claims_each_batch_once` |
| 108 tests pass | CI and local | `python -m pytest -q` |
| Nothing private is committed | pre-push privacy scan (keyed fingerprints of your terms) | `python scripts/privacy_scan.py` |
| Engine runs in containers from a data bank | compose services and named volumes | `docker ps`, `docker volume ls` (`regen-profile`, `regen-workspace`) |
