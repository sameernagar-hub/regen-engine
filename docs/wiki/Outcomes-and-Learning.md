# Outcomes and learning

**Thesis:** an application engine without feedback is a spam cannon. REGEN closes the loop: every reply is linked
back to the application, the resume lane and the facts that produced it. Every rejection is analyzed until a rule
explains it.

## The event log (`engine/feedback/events.py`)

- `workspace/events.jsonl`, append-only, one JSON object per line.
- Writes take a cross-process file lock, so three appliers and the API can append at the same time.
- Reads are incremental: consumers remember their byte offset.
- Every derived view (report, API, live view, graph, learn) is a pure function of this file, so any state can be
  rebuilt by replaying it.

## Inbox classification (`engine/feedback/inbox.py`)

`engine inbox <msgs.json>` (from a Gmail tab) or `engine inbox --imap [days]` (read-only IMAP) classifies recruiting
mail into **confirmation · OA · interview · rejection · offer · scam** with ordered patterns (including rejection
phrasing seen only in truncated snippets) and links each message to the application by company and role. The result
is an `outcome` event and a row in `workspace/outcomes.md`.

## Verified-only reporting

`engine report [date]` lists only applications whose latest status is `SUBMITTED` **and** whose proof screenshot
exists. Counts in the README and wiki come from this command. Nothing else is counted.

## `engine learn`

Response rates by lane and by ATS (applied, any reply, OA, interview, rejection) → `workspace/learnings.md`. This
is the reward signal for future strategy choices (lane, timing, source).

## The rejection log

Each rejection: read the body, re-read the stored JD (`workspace/jd/`), find the cause, add a fit-gate or form rule
and a test, and log it. See [Fit gate](Fit-Gate.md) for entries. Mis-submissions are logged the same way. One
example: a civil "Engineering Leader" title that passed the software title gate is now the first item to fix.

## Knowledge graph (`engine/memory`)

Facts ↔ skills ↔ projects ↔ roles ↔ jobs ↔ companies ↔ outcomes. `engine graph <term>` returns a node and its
neighbors, so you can ask which facts went into the applications that got replies.

Related: [Architecture](Architecture.md) · [Platform](Platform.md) · [Metrics](Metrics.md)
