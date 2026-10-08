# Truthfulness and safety

## What the engine may write about the candidate
| Output | Source | Gate |
|---|---|---|
| Resume bullets, projects, skills | Fact Bank entries, selected and ordered | `resume.validate()` rejects anything not in the bank |
| Skill spelling | the JD's spelling of a skill already listed ("Kubernetes (K8s)") | only from a fixed alias table; stripping aliases must give the original line exactly |
| Form answers | presets, approved answers, ordered rules | unset preset → the human queue |
| "Do you have experience with X?" | Yes only if X (or its meaning, e.g. SPA → React) is in the skills | never a guessed "No" |
| Open-ended answers (v0.8) | Fact Bank sentences chosen for this job | logged with fact ids in `drafts_review.md` and the event log |

## What is never drafted or guessed
Sponsorship, work authorization, citizenship, export control, arbitration, salary, EEO and demographics, references,
background checks, and anything sensitive (SSN, bank, passwords, date of birth). The draft module refuses these by
pattern before it looks at the Fact Bank, and the "answer from the page" API refuses them too.

### A worked example: "without sponsorship for the next 5 years"
A candidate on OPT is authorized to work **today** without sponsorship, but will need it later. A form asked "Are you
able to work in the US without visa sponsorship for the next 5 years?". The plain "authorized without sponsorship"
rule would have answered Yes, which isn't true. v0.8 adds a long-term variant whose answer is *derived* from the
presets (needs sponsorship in the future → No), and the legal airbag checks the same variant, so a "Yes" there now
stops the submission.

## Airbags (checked before every submit)
| Airbag | Trigger |
|---|---|
| Sensitive field | SSN, bank/routing, card, password, DOB, driver's license, passport, tax id |
| Payment | application or processing fee, card or billing details |
| Unexpected site | the form moved to a host that isn't an ATS or the job's own site |
| Answer drift | a legal answer differs from the presets |
| Rate caps | daily cap (default 25) and 3 per company per day |
| Kill switch | `workspace/STOP` exists |

A fired airbag records a flag, sends an SOS email if configured, screenshots the form, and moves on without submitting.

## Human checks
hCaptcha, reCAPTCHA, Cloudflare Turnstile and Ashby's automation flag are detected and handed to the candidate with
the form filled and the resume ready. After an Ashby flag, Ashby submissions pause for 24 hours.

## Privacy
`profile/` and `workspace/` are git-ignored. CI runs a privacy gate on every pull request and push (PII patterns,
forbidden paths, noreply-only commit emails, keyed fingerprints of private terms). The public demo is built from
anonymized events and refuses to publish if a company name would leak.
