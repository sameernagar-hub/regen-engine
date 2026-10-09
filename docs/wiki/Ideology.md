# Ideology

Job hunting tools tend to fail in one of two ways. Mass auto-appliers send the same resume everywhere and invent
answers to get past forms. Careful manual applying is honest but too slow: by the time a posting reaches the big job
boards, hundreds of people have applied. REGEN tries to be **fast and honest at the same time**.

## 1. Never invent. Only rearrange what is true.
Everything about the candidate comes from the **Fact Bank** (`profile/fact_bank.json`): accomplishments, roles,
projects and skills the candidate can prove. A resume can only *select and order* those facts. `resume.validate()`
rejects any resume that references something not in the bank, and the only wording change it allows is the job
description's spelling of a skill the candidate already lists ("PostgreSQL (Postgres)").

Drafted answers (v0.8) follow the same rule: the sentences are Fact Bank entries, rewritten only grammatically
("Built X" → "At Acme, I built X"). There is no language model in the loop that could make something up.

## 2. Legal answers are the candidate's, not the engine's
Work authorization, sponsorship, citizenship, arbitration and attestations come only from the candidate's presets.
If a form asks something the presets don't cover, the job waits for the candidate. An airbag stops any submission
where a legal answer drifts from the presets. Demographic questions are always declined.

## 3. Transparent by default
Every resume records the fact ids it used. Every skipped job records why. Every submission records every question,
every answer and a screenshot of the confirmation page. Every drafted answer records the facts it came from and is
listed for review. "Verified" means a submission whose proof screenshot exists on disk, nothing less.

## 4. Local-first
The profile and the runtime state stay on the candidate's machine and out of git. Network traffic is limited to
public job-board APIs and the forms being filled. There are no third-party services in the loop, and CI blocks any
commit that would leak personal data.

## 5. Lean
"Less effort, more output." Dead boards are skipped, lookups cached, logs read incrementally, and the hot paths are
measured (see [Algorithms](Algorithms.md)). The engine drives forms through their structure, not screenshots.

## 6. Respect the other side
CAPTCHAs, Cloudflare Turnstile and bot checks are never solved or bypassed; they go to the candidate with the form
filled. After a site flags automation, the engine stops submitting there for a day. Per-company and daily caps keep
the traffic of one careful person.

## 7. You start it
Since v0.8 there are no background schedules. The engine runs when the candidate starts it, and a `STOP` file halts
it at once.


Related: [Home](Home.md) · [Architecture](Architecture.md) · [Discovery](Discovery.md) · [Fit gate](Fit-Gate.md) · [Tailoring](Tailoring.md) · [Apply engine](Apply-Engine.md) · [Email codes](Email-Codes.md) · [Outcomes](Outcomes-and-Learning.md) · [Platform](Platform.md) · [Metrics](Metrics.md)
