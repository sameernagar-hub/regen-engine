# Email codes

Greenhouse often asks for an 8-character security code that it emails right after the first submit. With several
tabs and appliers in flight, several jobs can wait at once, sometimes two at the same company. This page explains
how the engine gets each job its own code.

## Protocol

```mermaid
sequenceDiagram
    participant J as Job (tab)
    participant FS as workspace/codes
    participant M as Matcher (engine codes)
    participant G as Inbox
    J->>FS: write <board>_<id>.wait (company, form URL)
    G-->>M: codes [{company, code, when}] (Gmail tab script or IMAP)
    M->>FS: <slug>.txt = code; append code to <slug>.tried
    FS-->>J: poll every 1 s (round-robin wait, other tabs keep working)
    J->>J: type code, submit
    alt code bounced
      J->>FS: rewrite .wait (re-wait)
      M->>FS: next unused code, never one in .tried
    end
```

## Matching rules (`engine/apply/codes.py`)

- **Same company only.** The email must name the job's company (normalized compare), so a code is never typed into
  another company's form.
- **Fresh only.** The email must arrive after the job started waiting, with a 3-minute margin for round-robin delay
  between the submit click and the `.wait` file. After a bounce the window widens by 10 minutes.
- **One code per job.** The oldest waiter gets the oldest unused code, and no code is assigned to two jobs in one pass.
- **Never resend a bounced code.** `<slug>.tried` remembers codes already sent to that job.

Why the last two rules exist: Gmail threads same-subject emails, so two applications to one company can show both
codes in one conversation row with one timestamp, and arrival order alone picked the wrong pairing once. The tab
script `regenCodes` now reads every code in each thread through Gmail's print view.

## Sources of codes

| Mode | How | Needs |
|---|---|---|
| Gmail tab | `engine/discovery/gmail_codes.js` (or the thread-aware `regenCodes`) → `python -m engine codes '<json>'` | a signed-in Gmail tab |
| **Hands-free** | `python -m engine codes --watch`: read-only IMAP (`BODY.PEEK`, never marks or moves mail), one SEARCH per poll, only while a job waits | Gmail app password in `.env` |
| MCP | `submit_codes` tool (`REGEN_MCP_WRITE=1`) | an MCP client |

Cost: O(waiting × codes) per poll, both tiny. One IMAP login per watch session.

Related: [Apply engine](Apply-Engine.md) · [Running the engine](Running.md) · [Configuration](Configuration.md)
