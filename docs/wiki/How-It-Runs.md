# How it runs: AI, resumes, containers, MCP

This is the working manual: what happens to one job from discovery to the confirmation page, and who does each step.

## 1. Where AI is used (and where it isn't)
REGEN needs **no model API key**. Every step that touches a form or a resume is deterministic code, so it's
reproducible and testable. AI comes in only through **your own AI client over MCP** (Claude, Cursor, ChatGPT): it
starts runs, reads the queue, drafts answers to new questions *from your Fact Bank*, records inbox outcomes, and fixes
rules. Everything it writes goes through the same validators as code.

| Step | Done by | Why |
|---|---|---|
| Discovery, fit gate, priority | code (`engine/discovery/`, `engine/pipeline.py`) | rules you can read and test |
| Resume composition | code (`engine/tailoring/`) | every line must trace to a Fact Bank id |
| Form answers | rules, then saved answers, then Fact Bank drafts (`engine/apply/runner.py`, `drafts.py`) | the same question always gets the same answer |
| New questions, rejection analysis, new rules | your AI client over MCP, or the user | judgment, but the output is checked |
| Legal, EEO, export-control, arbitration | **only you** (presets) | never inferred |

## 2. How a resume is made (`engine/tailoring/`)
1. **Read the JD:** HTML is unescaped, blockers are checked (sponsorship, clearance, years, grad window), and the JD terms
   you actually have (`want`) are found by intersecting the JD with your Fact Bank vocabulary.
2. **Pick the lane** (backend, AI, data, SRE, embedded…) by title and JD words; the lane gives the default fact order.
3. **Rank facts** within each role by how many `want` terms they hit; overlap groups stop near-duplicate bullets.
4. **Skills:** each line is reordered JD-first in the posting's spelling. The *coverage fill* adds up to 2 more of your
   own skills lines for terms the page still misses.
5. **Headline and summary:** the role name plus the posting's top 3 terms; summary sentences are your own, best match first.
6. **Validate and render:** the validator rejects any line that isn't from the Fact Bank; the PDF is one page.
7. **ATS read-back:** the PDF's extracted text is checked for the JD terms (`ats.score`), and coverage is logged as a
   `resume` event.

## 3. How containers are assigned work (`deploy/bank.compose.yml`)
```
pipeline (1)  scan -> prune -> select (bands + heap, per-company cap, Ashby cap) -> build resumes
              -> split into REGEN_PARTS parts (round-robin: each part mixes companies and ATSs)
              -> write each part as .name.json, then rename into batches/inbox (atomic appearance)
applier (N)   loop: claim = create claimed/<part>.lock exclusively (O_CREAT|O_EXCL, one winner)
              -> move the part to claimed/ -> engine apply (headed Chromium, REGEN_TABS tabs round-robin)
              -> move to done/, drop the lock
relay (1)     codes from the Gmail feed tab -> codes/<board>_<id>.txt for whichever worker is waiting
```
- **Who gets what:** the first free worker claims the oldest part. Nothing is pinned to a worker, so a slow form never
  idles the others.
- **Rate limits are central:** selection runs once, so per-company and per-ATS limits hold whatever N is.
- **Failure:** a dead worker leaves its part in `claimed/`. The pipeline's wait times out and the next pass re-selects the
  unfinished jobs (submitted ones are skipped).
- **Stop:** `workspace/batches/STOP` makes every worker exit after its current part.

## 4. One job's life
`scan` finds it, then `prune` keeps it if fillable, then `select` ranks it (band, score), then `build` writes the
resume and the batch entry, then a worker claims the part, then the tab opens the form, then answers are filled
(rules, saved answers, drafts), then the resume is uploaded, then submit. If an email code is needed the job waits on
`codes/*.wait` and the relay delivers the code. Then the confirmation page is checked, a proof screenshot is taken and an
`application` event is written to `events.jsonl` (status, answers, resume, proof). Later, inbox outcomes become
`outcome` events and lane reply rates feed back into priority.

## 5. MCP in every container
The image includes the MCP server, so each container is also an MCP endpoint over stdio. In your MCP client:
```json
{ "mcpServers": {
  "regen-pipeline":  { "command": "docker", "args": ["exec", "-i", "deploy-pipeline-1",  "python", "-m", "engine", "mcp"] },
  "regen-applier-1": { "command": "docker", "args": ["exec", "-i", "deploy-applier-1", "python", "-m", "engine", "mcp"] }
} }
```
Every container sees the same bank, so any of them answers `control_state`, `needs_by_question`, `priority_explain`,
`factbank`, `trust_check`. Write tools (`answer_save`, `run_start`, `inbox_record`) need `REGEN_MCP_WRITE=1` on that
container.
