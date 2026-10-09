# Apply engine

**Thesis:** filling forms is an I/O-bound scheduling problem with a correctness core. The scheduling half keeps
every browser tab busy. The correctness half guarantees that each answer comes from a source the user approved, or
the job stops before submitting.

## Adapters (`engine/apply/runner.py`)

| ATS | Fill | Submit and confirm | Special cases |
|---|---|---|---|
| Greenhouse (hosted + embed) | text, react-select comboboxes, radios, checkboxes, file upload, EEO wrappers | "Thank you" page; **email security code** step | hidden phone-country list filtered out of dropdown options; per-job code files |
| Ashby | Yes/No buttons, CSS-only required markers, follow-up questions (second pass) | resubmit once on "Missing entry" | bot-check → 24 h cooldown for all Ashby jobs |
| Lever | location autocomplete limited to your state, EEO selects | confirmation text | hCaptcha → human queue |
| Workable | text, radios, uploads | confirmation text, 60 s wait | Cloudflare Turnstile → human queue; `REGEN_SKIP_ATS=workable` when it bot-walls |

Each adapter is a **generator**: it `yield`s at every field (a checkpoint) and at every wait (`yield <seconds>`), which
is what lets the scheduler interleave many forms.

## The answer resolver

For every field label the resolver tries, in order:

1. **Per-job extras** (for example an approved arbitration acknowledgement for one employer).
2. **Your approved answer bank** (`profile/answers.json`).
3. **Ordered rules** (~90 regex → preset rules). Order is semantics: acknowledgements before salary, SMS opt-in before
   email, "(City, State)" before country, generic "N years" before skill questions.
4. **Derived answers** computed from facts: total years vs "N or more years" (generic questions only), years lived in
   the US, time zone match, "able to start within N days" from the notice period.
5. **Job note** for "why us / cover letter", written per job from Fact Bank entries.
6. **Drafted answer** for open questions (`drafts.py`): sentences built only from the facts the job's resume chose,
   logged with fact ids in the event and in `drafts_review.md`.
7. **Yes/no autofill policy**: willingness questions → your onsite/relocation stance. "Have you / do you have" →
   Yes only if a Fact Bank entry backs it, else No. **Status questions are never defaulted** (sponsorship,
   authorization, citizenship, export, arbitration, salary, EEO, criminal, government, relatives, prior employment).
8. Nothing → the field is left for you and the job ends `NEEDS YOU` with the exact labels.

Special tokens: `__DECLINE__` (EEO: pick the decline option), `__ACK__` (pick an affirmative acknowledgement, never
a negative one), `__SKILLS__` (multi-select: tick only options your skills name).

## Dropdown matching (`pick_option`)

Exact → prefix → contains → whole-word containment of a short option → sentence-form "No" ("I have never been
employed by…") → preferred-location fallback → **aliases** (same fact spelled differently: "United States of
America", "M.S.", visa-type spellings, careers-page synonyms) → **salary buckets** (a number picks the range that
contains it: `$80,000 – $100,000`, `120,000+`). If nothing matches, the field stays empty and the job goes to you.

## Scheduler (`engine/apply/scheduler.py`)

Preemptive round-robin over `REGEN_TABS` tabs. A job runs until its **time quantum** is used (back of the ready
queue) or it yields a wait (sleeps on a heap until its wake time). Quantum per ATS = EWMA mean + 0.84 σ of observed
CPU bursts (80th percentile), clamped 2–20 s and persisted. Pick O(1), preempt O(1), sleep/wake O(log S). Measured
×2.05 throughput over sequential on a seeded simulation, ×2.5 with 4 tabs. Batches are interleaved by company so
rate limits and bot checks see spread-out traffic.

## Airbags (`engine/safety.py`), before every submit

- Sensitive fields (SSN, bank, date of birth, driver's license, ...) → `FLAGGED`.
- Unexpected site or redirect → `FLAGGED`.
- Legal answers that drift from presets → `FLAGGED`.
- Rate caps: `REGEN_MAX_PER_DAY` (default 25) and 3 per company per day.
- Kill switch file stops everything.

## Proof

Every attempt ends with a full-page screenshot in `workspace/proof/`. A submission counts as **verified** only if the
latest status is `SUBMITTED` *and* the proof file exists (`engine report`).

Related: [Email codes](Email-Codes.md) · [Tailoring](Tailoring.md) · [Truthfulness and safety](Truthfulness-and-Safety.md) ·
[Algorithms](Algorithms.md) · [Configuration](Configuration.md)
