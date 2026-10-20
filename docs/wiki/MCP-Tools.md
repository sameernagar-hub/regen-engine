# MCP tools

Every tool the engine exposes over MCP (43 tools), grouped by the engine level it drives. This page is generated from
`engine/connectors/mcp_server.py` (`/api/control/mcp` returns the same catalog live), so it matches the code.

- **read** tools are always on.
- **write** tools need `REGEN_MCP_WRITE=1` on the server (the Docker start command sets it for the bank MCP). The kill
  switch always works.
- Two servers expose the same tools: `regen-bank` (HTTP, `http://127.0.0.1:8790/mcp`, the live bank in Docker) and
  `regen-engine` (stdio, `python -m engine mcp`, started by your AI client). See [Zero cost: your AI runs it](Zero-Cost-and-MCP).

## Discovery (8)

| Tool | Kind | What it does |
|---|---|---|
| `job_queue` | read | Jobs discovered and waiting in the queue (not yet applied), optionally filtered by a word in company/title. |
| `priority_explain` | read | Why the queue is ordered the way it is: the top N jobs with their priority score and its parts (level, lane, freshness, employer tier, sponsor, learned reply rate). |
| `discovery_sources` | read | Discovery sources: boards watched per ATS, queue size, built-in and added job-list feeds, and the last sources added (by whom). Start here before looking for new places to find jobs. |
| `boards_add` | write | Watch new employer boards: pass job or board URLs on any ATS the engine knows (Greenhouse, Ashby, Lever, Workable, SmartRecruiters, Workday, iCIMS, Rippling, JazzHR). Max 50 per call; the next pipeline pass scans them. Needs REGEN_MCP_WRITE=1. |
| `feed_add` | write | Add a job list (a README or JSON on https, e.g. a GitHub new-grad list) whose links point at ATS boards: harvested now and on every `engine harvest`. Needs REGEN_MCP_WRITE=1. |
| `companies_probe` | write | Company names (max 50) -> probe the ATSs whose board tokens can be guessed; boards with open jobs are watched from the next pass. Use it on companies you found hiring elsewhere. Needs REGEN_MCP_WRITE=1. |
| `leads_add` | write | Job leads seen anywhere (job sites, posts, newsletters): [{company, title, url?}] (max 50). Each is matched on the employer's own ATS and queued; the fit gate still decides. Needs REGEN_MCP_WRITE=1. |
| `harvest_now` | write | Harvest every job-list feed (built-in + added) for new ATS boards now. Needs REGEN_MCP_WRITE=1. |

## Fit gate (6)

| Tool | Kind | What it does |
|---|---|---|
| `filters_get` | read | Title/company filters (regex alternations) and the years-of-experience gate from presets. |
| `filters_set` | write | Replace include_titles / exclude_titles / exclude_companies (regex; each must compile; old file kept as .bak-ui). Needs REGEN_MCP_WRITE=1. |
| `trust_check` | read | Trust gate for one posting: is the application host an employer-controlled ATS, and does the description carry job-scam red flags? Returns {ok, reasons}. |
| `feedback_rules` | read | Rejection feedback: what rejected job descriptions asked for that the others did not, each phrase's evidence (rejected / seen / lift / adjusted p) and status (active blocks, proposed is watched). |
| `fit_check` | read | Run the fit gate on a job description (and title): hard blockers found (sponsorship, years, clearance, stack, learned rejection phrases...) and whether the title passes your filters. |
| `feedback_rule_off` | write | Stop a learned rejection phrase from blocking postings (the feedback loop keeps it off). Needs REGEN_MCP_WRITE=1. |

## Pipeline (6)

| Tool | Kind | What it does |
|---|---|---|
| `pipeline_status` | read | Live pipeline status: each applier log's last results, jobs waiting for a Greenhouse email code, and today's verified count. |
| `pipeline_run` | write | Start the whole pipeline in the background (discover, select, build, apply, report). Needs REGEN_MCP_WRITE=1. Returns the log path; watch it with pipeline_status. |
| `submit_codes` | write | Deliver Greenhouse security codes read from the inbox: codes = [{company, code, when}]. A code only goes to the waiting job whose company the email names, and only if it was sent after the job started waiting. Needs REGEN_MCP_WRITE=1. |
| `run_start` | write | Start a run the way the control room does: {days, max, appliers, tabs, cap, loop (minutes, 0 = one pass), scan, newgrad, feed, ats: [greenhouse, lever, ashby, workable], dry}. Needs REGEN_MCP_WRITE=1. |
| `run_stop` | write | Stop the run started by run_start / the control room (kills its process tree). Needs REGEN_MCP_WRITE=1. |
| `control_state` | read | Live control-room state: the current run's steps, each active applier's tabs (job + state), latest answers, queue size by ATS, and when Ashby reopens. |

## Needs you (6)

| Tool | Kind | What it does |
|---|---|---|
| `human_queue` | read | What only the human can do right now (each job's latest state): personal questions, bot checks, missing answers. |
| `needs_by_question` | read | What's waiting on the user, grouped by blocking question (answer one question to unblock many jobs). |
| `answer_save` | write | Save the user's answer to a blocking question (reused on every form that asks it; legal / EEO / sponsorship questions are refused: those come from presets only). Needs REGEN_MCP_WRITE=1. |
| `inbox_record` | write | Record recruiting emails the assistant read from the user's inbox: messages = [{date, from, subject, snippet}]. Classifies confirmation / rejection / OA / interview / offer / scam and links them to applications. Needs REGEN_MCP_WRITE=1. |
| `answer_queue_add` | write | Queue an answer to a blocking question (the answers container saves it and retries the job). Legal / sponsorship / EEO / sensitive questions are refused. Needs REGEN_MCP_WRITE=1. |
| `answer_queue_status` | read | Answer queue state: waiting, claimed, done and refused counts, plus the latest refusals. |

## Gearbox (2)

| Tool | Kind | What it does |
|---|---|---|
| `gearbox_status` | read | The gearbox: current gear (N, 1-4), the clutch, what they set (applier range, scan interval), live speed (submissions in the last hour / 24 h) and the rejection feedback's learned rules. |
| `gear_shift` | write | Shift the engine: gear N (idle), 1 (crawl) .. 4 (overdrive), and/or clutch on/off (learned rejection phrases block postings or not). Safety caps are not gears. Needs REGEN_MCP_WRITE=1. |

## Memory + Fact Bank (6)

| Tool | Kind | What it does |
|---|---|---|
| `engine_status` | read | Proof-backed counts: verified applications (total/today), items waiting on the human, boards watched, outcomes. |
| `applications` | read | Applications, newest first. status: SUBMITTED, NEEDS YOU, FAILED, FLAGGED or SKIPPED (empty = all). |
| `outcomes` | read | Inbox outcomes the engine classified (confirmation, rejection, oa, interview, offer, scam), newest first. |
| `memory_query` | read | Knowledge-graph lookup. Pass a company name, a Fact Bank id (e.g. 's_rag') or a lane ('backend'). Returns the node and everything connected to it (applications, facts used, questions answered, outcomes). |
| `factbank` | read | The Fact Bank: every fact with how many resumes used it and in which lanes, plus roles, projects, skills, education and where each fact came from. The only source the engine writes from. |
| `outreach_drafts` | write | Outreach drafts for recent submissions at tier companies and startups: subject, body (template lines + Fact Bank entries that application's resume used), and a Gmail compose link. Nothing is sent; the user adds the recipient. rebuild=True regenerates them (needs REGEN_MCP_WRITE=1). |

## Fleet (6)

| Tool | Kind | What it does |
|---|---|---|
| `fleet_status` | read | Fleet health from the bank: every container's heartbeat (pipeline, appliers, relay, supervisor), batch queue (inbox/claimed/done), codes waiting, problems, whether the kill switch is on, and the applier min/max. Read-only. |
| `kill` | write | KILL SWITCH: stop all processing now. Workers stop after their current step, appliers and the pipeline are stopped, the supervisor holds until clear_kill. Always allowed (stopping is safe); give the reason you saw. |
| `clear_kill` | write | Lift the kill switch after the cause was investigated (check quarantine_list and audit_log first). Appliers come back as the supervisor scales to the backlog. Needs REGEN_MCP_WRITE=1. |
| `audit_log` | read | The supervisor's audit trail (start/create/remove/requeue/KILL/clear/limits), newest last. |
| `quarantine_list` | read | Files the leak guard moved to quarantine (name, size, time; never contents). |
| `scale` | write | Set how many appliers the supervisor may run (min..max, hard cap 12; 0..0 parks the fleet without a kill). Kept across restarts. Needs REGEN_MCP_WRITE=1. |

## Ledger (2)

| Tool | Kind | What it does |
|---|---|---|
| `ledger_tables` | read | Ledger tables and views (events, applications, answers, codes, outcomes, resumes, discoveries, supervisor_audit, fleet_heartbeats) with row counts and columns. Read-only. |
| `ledger_rows` | read | Rows from one ledger table, newest first. q = text anywhere in the row; col + val = one column contains val (e.g. name='applications', col='company', val='acme' to see if an application reached the ledger). limit <= 1000. Read-only. |

## Repo (1)

| Tool | Kind | What it does |
|---|---|---|
| `reposync_status` | read | Repo-sync container: its last heartbeat (feed / code state, open PR) and its last audited actions. |

Related: [Zero cost: your AI runs it](Zero-Cost-and-MCP) · [Discovery](Discovery) · [Gearbox](Gearbox) · [Platform](Platform)
