# How it works

```
 listen ──► judge ──► write ──► apply ──► hear back
 (ATS APIs)  (fit gate) (resume)  (forms)   (inbox)
```

## 1. Listen: discovery (`engine/discovery/`)
- **ATS boards.** Greenhouse, Ashby, Lever and Workable publish job boards as JSON. A registry of about 2,300 boards
  is polled; postings from the last N days that pass the domain filter (title, level, US location, employers to skip)
  go to `workspace/queue.json`. Dead boards are remembered and skipped.
- **Leads from elsewhere.** New-grad job lists and job-alert emails name roles but hide the employer's own posting.
  The engine resolves each lead to the company's ATS board and matches the title there, so the application goes to
  the employer, not an aggregator.

## 2. Judge: the fit gate (`engine/tailoring/tailor.py: fit`)
Each job description is read for hard blockers before any work is spent on it: citizenship or ITAR, security
clearance, "no sponsorship", graduation windows, years of experience above the candidate's, and a required core
stack the candidate doesn't have. Skips are logged with the reason and never re-queued. These rules came from
reading real rejections against their job descriptions.

## 3. Write: tailoring (`engine/tailoring/`)
Each job gets its own resume: the lane (backend, AI, full-stack, data, platform...) decides the shape, then facts,
projects and skills lines are ranked by how many of the job's technologies they mention. Versions of the same
accomplishment never appear twice. The result is validated against the Fact Bank and rendered to PDF.

## 4. Apply (`engine/apply/`)
- **Round-robin over tabs.** Several applications run at once, each in its own browser tab, each as a generator that
  pauses at every field and every wait. See [Algorithms](Algorithms.md).
- **Answers.** Per-job extras → approved answers → presets via ordered rules → experience questions from the skills
  list → drafted answers for open-ended questions. Anything else goes to the candidate.
- **Airbags** before every submit, then the submit, the confirmation check and a proof screenshot.
- **Email codes.** Greenhouse sometimes emails a code. Each waiting job writes its own `.wait` file; a code from the
  inbox is only given to the job whose company the email names.

## 5. Hear back: feedback (`engine/feedback/`)
Recruiting email is classified (confirmation, rejection, online assessment, interview, offer, scam) and linked to the
applications it is about. `learn` reports response rates by lane and ATS; rejections are read against their job
descriptions and turned into new fit-gate rules.

## The evidence
Everything above writes to one append-only event log. The API, the live view, the memory graph and the public demo
are all derived from it; nothing else is a source of truth.


Related: [Home](Home.md) · [Architecture](Architecture.md) · [Discovery](Discovery.md) · [Fit gate](Fit-Gate.md) · [Tailoring](Tailoring.md) · [Apply engine](Apply-Engine.md) · [Email codes](Email-Codes.md) · [Outcomes](Outcomes-and-Learning.md) · [Platform](Platform.md) · [Metrics](Metrics.md)
