# Fit gate

**Thesis:** the cheapest application is the one you never send. Before a resume is built or a form is opened, the
job description is checked against hard eligibility rules. A blocked job is logged as `SKIPPED` with its reasons,
so every skip can be audited.

## Pipeline position

`build()` fetches every JD in parallel, then for each job: `fit(jd)` → blockers? → skip and record : route to a lane
→ tailor. The fit gate runs on text only (no browser), in microseconds per JD.

## Rules

| Blocker | Typical JD phrasing | Source of truth |
|---|---|---|
| `citizenship` | "U.S. citizenship required", "U.S. person (ITAR)" | presets: citizenship, ITAR status |
| `clearance` | "active Secret / TS/SCI", "ability to obtain a clearance" | presets: no clearance |
| `no sponsorship` | "unable to sponsor", "must be authorized without sponsorship now or in the future" | presets: needs sponsorship later |
| `N+ yrs` | "4+ years of professional experience" | presets: years of experience |
| grad window | "graduating Dec 2026–Jun 2027", "degree by May 2027", "currently enrolled" | Fact Bank: graduation date |
| `core stack: X` | the posting is built on a language or platform absent from the Fact Bank | Fact Bank skills |

**Preprocessing matters.** Greenhouse returns JDs HTML-escaped (`&lt;p&gt;`, `&#39;`). Matching raw text hid
"no sponsorship" phrases until the gate began unescaping twice before matching. That fix came straight from a
rejection analysis.

## The rejection loop

Every rejection that arrives in the inbox is read, the JD is re-checked, and when a rule would have caught it, the
rule and a regression test are added. Examples from the log:

| Rejection | Cause in the JD | Fix |
|---|---|---|
| "SWE II" roles | 4+ years required | years rule uses the presets' years |
| A "modern C++" role | core stack missing from the Fact Bank | core-stack blocker |
| A campus development program | "Bachelor's by May/June 2027" | grad-window catches "degree by 2027/2028", "currently enrolled" |
| A fintech role | "no sponsorship", hidden by HTML escaping | double `html.unescape` before matching |

The gate is deliberately strict: a skipped good job costs one opportunity, while a doomed application costs a
resume, a form, an email code and a reply-rate signal.

## Interaction with the form

Some eligibility questions only appear on the form. Those are answered from presets (see
[Apply engine](Apply-Engine.md)), and a mismatch at that point stops the job (`NEEDS YOU` / airbag) instead of
submitting an answer the user hasn't approved.

Related: [Discovery](Discovery.md) · [Tailoring](Tailoring.md) · [Truthfulness and safety](Truthfulness-and-Safety.md)
