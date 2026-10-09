# Running the engine

## A day's run
```bash
python -m engine scan 1                          # every registered board, postings from the last 24 h
python -m engine newgrad 1                       # new-grad leads resolved to employer ATS boards
python -m engine batch b1 <id,id,...>            # fit gate + one tailored resume per job
REGEN_TABS=3 python -m engine apply batches/b1.json
python -m engine report                          # verified submissions only (proof on disk)
```
Settings: `REGEN_TABS` (tabs in the round-robin, default 3), `REGEN_PW_PROFILE` (browser profile folder, so a second
applier can run next to the first), `REGEN_MAX_PER_DAY` (daily cap, default 25), `REGEN_DRAFT=0` (send open-ended
questions to you instead of drafting).

## Greenhouse email codes
1. A job reaching the code step writes `workspace/codes/<board>_<id>.wait` (company and form URL) and keeps waiting
   while the other tabs work.
2. In a signed-in Gmail tab, run `engine/discovery/gmail_codes.js`; it returns `[{company, code}]` from the search
   rows without opening any message.
3. `python -m engine codes '<that json>'` writes each code only to the job whose company the email names.

## Reading the inbox
Save recruiting emails as `[{id, date, from, subject, snippet}]` and run `python -m engine inbox <file>`, or use
`python -m engine inbox --imap 3` with an app password in `.env`. Then `python -m engine learn`.

## Answering what the engine couldn't
- `workspace/human_queue.md` and the live view's "waiting on you" list each job's unanswered questions.
- With `REGEN_API_WRITE=1` on the local API, answer them in the page. Answers go to `profile/answers.json` with their
  source and are reused; the job lands in `batches/requeue.json`.

## Stopping
Create `workspace/STOP`. The applier stops before the next job; delete the file to resume.

## Tests and evidence
```bash
python -m pytest -q --cov=engine --cov=apps/api        # unit, API and headless form tests
python scripts/bench_scheduler.py 20 3                 # scheduler speed-up (deterministic)
python scripts/bench_tailor.py <old tailor.py>         # identical output + speed vs an older version
```


Related: [Home](Home.md) · [Architecture](Architecture.md) · [Discovery](Discovery.md) · [Fit gate](Fit-Gate.md) · [Tailoring](Tailoring.md) · [Apply engine](Apply-Engine.md) · [Email codes](Email-Codes.md) · [Outcomes](Outcomes-and-Learning.md) · [Platform](Platform.md) · [Metrics](Metrics.md)
