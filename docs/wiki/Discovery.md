# Discovery

**Thesis:** a role exists first on the employer's applicant tracking system (ATS). Aggregators re-publish it hours to
days later. Discovery therefore polls the ATS directly and treats every other source as a *lead* that has to be
resolved back to the employer's own posting before anything is applied to.

## Sources

| Source | Mechanism | Calls | Code |
|---|---|---|---|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | 1 GET / board | `ats.py`, `scan.py` |
| Ashby | public posting API per board | 1 / board | `ats.py` |
| Lever | `api.lever.co/v0/postings/{company}?mode=json` | 1 / board | `ats.py` |
| Workable | public widget API | 1 / board | `ats.py` |
| Job-alert emails | `gmail_alerts.js` runs inside your signed-in Gmail tab, reads LinkedIn, Indeed, Glassdoor, ZipRecruiter, Handshake, Monster and Ladders alerts through Gmail's print view; extracts title, company, location only | 0 external | `gmail_alerts.js`, `alerts.py` |
| newgrad-jobs.com | listing pages → leads | few GETs | `newgrad.py` |
| SimplifyJobs | `listings.json` (community new-grad list) | 1 GET | `simplify.py` (`engine feed`) |
| Big-tech careers APIs | Amazon `search.json` (full JD inline), NVIDIA Workday `cxs` (search + 1 GET per kept job) | ~8 + kept | `bigtech.py` |

## Board registry

`workspace/boards.json` holds ~2,370 boards across the four ATSs. `engine boards harvest` grows it from public GitHub
job lists; boards that 404 are marked dead and skipped (`engine boards recheck` retries them). A full scan runs the
boards in parallel threads, so wall time is roughly the slowest board rather than the sum. A full scan returns ~3,400
fresh postings before filtering.

## Lead resolution

A lead is `(company, title, location)` with no ATS link (alert emails, newgrad pages). Resolution:

1. Normalize the company name (drop Inc/LLC, punctuation) and look it up in the board registry, then try likely slugs.
2. Fetch that board once (cached per run) and match the title by normalized token overlap.
3. Only a match on the employer's own board becomes a queue entry; everything else stays in `alert_leads.json` /
   `leads.json` for the user, with the reason.

Staffing agencies and aggregators are dropped (they don't name the employer). Results: one day's alert emails
gave 90 listings → 45 relevant → 6 resolved to an ATS job; a newgrad pull gave 215 leads → 34 resolved.

## Domain filter

`engine/discovery/filters.py` + `profile/domains.json`:

- **include_titles / exclude_titles**: target roles in, seniority and off-domain titles out (senior, staff, principal,
  manager, clearance, PhD, CNC, ...). Broad words only count with a software context.
- **exclude_companies**: employers you can't or won't apply to (defense primes, federal contractors that require
  clearance or citizenship).
- **US-only location logic**, including "Remote" roles whose title names a non-US city.
- **Already applied**: `workspace/ids.txt` and the event log dedupe by posting id and URL.

## Watcher

`engine watch <min> [--newgrad]` polls on an interval and announces only brand-new postings, with minutes since they
went live, optionally to a webhook (`REGEN_WEBHOOK`). It ships as a small Docker service
(`deploy/watcher.compose.yml`). By the user's decision the engine never schedules itself: runs start when the user
says so.

## Big tech

The largest employers run their own portals behind a candidate account. REGEN doesn't create accounts or sign in, so
`engine bigtech` does everything up to the submit: it polls the public search APIs, applies the same domain filter
and fit gate, builds the tailored resume and writes `workspace/bigtech.md` (link, posted date, lane, ATS score,
resume path). Re-runs only fetch new postings (`bigtech_seen.json`). On the first run 43 roles passed.

## Complexity

Scan: O(B) requests for B boards, parallel. Filter: O(P) postings with precompiled regexes. Lead resolution:
O(L) leads, with one cached board fetch per company. Dedupe: O(1) set lookups.

Related: [Fit gate](Fit-Gate.md) · [Architecture](Architecture.md) · [Configuration](Configuration.md) ·
[Running the engine](Running.md)
