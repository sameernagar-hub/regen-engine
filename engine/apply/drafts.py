"""Drafted answers for open-ended questions, built only from Fact Bank entries (no LLM, no network).

Policy (user, 2026-10-07): don't park a job on "Why us?" / "Describe a time..." questions; draft the best
answer and move on. The engine principles still hold: every sentence that states something about the
candidate is a Fact Bank entry (rewritten only grammatically: "Built X" -> "At <employer>, I built X"),
the facts are the ones the tailored resume already chose for this JD (so they're the most relevant),
and every draft is logged with its fact ids (event field `drafted`) and listed in workspace/drafts_review.md
so you can read exactly what was sent.

Never drafted: legal / sponsorship / authorization / arbitration / EEO / salary / sensitive questions.
Those come from presets or go to the human queue, as before.

Cost: O(F) to load the job's spec (F = facts on its resume, <= ~15) and O(L) regex work on the label,
so drafting is microseconds next to a page load.
"""
import datetime, json, os, re

OPEN = re.compile(r"\b(why|what|describe|tell us|tell me|how (do|did|would|have)|share|explain|walk us|anything else|provide (some |a few )?examples?|examples? of|"
                  r"cover letter|if you had|give an example|example of|talk about|proud|built|interest(ed|s)? you|excit)", re.I)
NEVER = re.compile(r"sponsor|authori[sz]|visa|citizen|immigration|arbitrat|salary|compensation|pay\b|gender|race|ethnic|"
                   r"veteran|disab|pronoun|ssn|social security|date of birth|criminal|convict|background check|clearance|"
                   r"reference|phone|e-?mail|address|linkedin|github|website|url|\bname\b", re.I)

KINDS = [  # (kind, label regex) first match wins
    ("built", r"examples? of|provide (some |a few )?examples|experience (with|in)"),  # before "learn": "Machine Learning"
    ("persist", r"kept pushing|persist|challenge|difficult|obstacle|setback|fail|hard problem|stuck|gave up|stopped"),
    ("learn", r"learn|one month|no obligations|curious|outside of work|free time|spend (it|a month)"),
    ("ai", r"\bai\b|llm|chatgpt|claude|copilot|cursor"),
    ("built", r"built|build|proud|project|accomplish|achievement|shipped|created|impact|examples? of|experience with"),
    ("why", r"why|excit|interest|motivat|draw|attract|cover letter|join"),
]
PERSIST_FACT = re.compile(r"rebuil|failing|failure|incident|silent|root cause|outage", re.I)


def _clean(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    t = t.replace(" -- ", ", ").replace("--", ", ")
    return " ".join(t.split()).rstrip(".")


def _sentence(fid, fb, prev=None):
    """'Built and deployed X.' (role acme) -> 'At Acme Corp, I built and deployed X.'
    A second fact from the same employer reads 'I also built ...'."""
    text = _clean(fb["facts"].get(fid, ""))
    if not text:
        return None
    prefix = fid.split("_")[0]
    role = next((v for k, v in fb.get("roles", {}).items() if k.startswith(prefix)), None)
    verb = text[0].lower() + text[1:]
    if role and prev and prev.split("_")[0] == prefix:
        return f"I also {verb}."
    return (f"At {role[0]}, I {verb}." if role else f"I {verb}.")


def _spec(job, workspace):
    """The tailored resume spec for this job: its fact ids are already ranked by JD overlap."""
    res = os.path.basename(job.get("resume") or "")
    m = re.match(r"Resume_(.+)\.pdf$", res)
    if not m:
        return None
    p = os.path.join(workspace, "specs", m.group(1) + ".json")
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ranked_facts(job, fb, workspace):
    sp = _spec(job, workspace)
    if sp:
        out = [f for _, fids in sp.get("roles", []) for f in fids]
    else:
        out = list(fb.get("facts", {}))
    return [f for f in out if f in fb.get("facts", {})]


def is_open(label):
    l = " ".join((label or "").split())
    return bool(l) and bool(OPEN.search(l)) and not NEVER.search(l)


def kind_of(label):
    for k, rx in KINDS:
        if re.search(rx, label, re.I):
            return k
    return "why"


def draft(label, job, fb, workspace, presets=None):
    """-> (answer text, [fact ids]) for an open-ended question, or None when it must not be drafted."""
    if not is_open(label):
        return None
    facts = ranked_facts(job, fb, workspace)
    if not facts:
        return None
    company, _, title = (job.get("name") or "").partition(" - ")
    company, title = company.strip() or "your team", title.strip() or "this role"
    k = kind_of(label)
    persist_fact = None
    if k == "persist":
        persist_fact = next((f for f in facts if PERSIST_FACT.search(fb["facts"][f])), None)
        if not persist_fact:  # the resume for this job has none: look in the whole bank
            persist_fact = next((f for f in fb["facts"] if PERSIST_FACT.search(fb["facts"][f])), None)
        pick = [persist_fact] if persist_fact else facts[:1]
    elif k == "ai":
        pick = [f for f in facts if re.search(r"agent|llm|rag|aitools|genai", f + fb["facts"][f], re.I)][:2] or facts[:2]
    else:
        pick = facts[:2]
    body = " ".join(s for s in (_sentence(f, fb, pick[i - 1] if i else None) for i, f in enumerate(pick)) if s)
    if k == "why":
        text = f"The {title} role lines up with the work I already do. {body} I'd like to bring that experience to {company}."
    elif k == "persist":
        # the closing restates the fact's own outcome only when the fact says it was fixed and tested
        tested = persist_fact and re.search(r"test", fb["facts"][persist_fact], re.I)
        text = body + (" I stayed with it until the cause was found and pinned down with tests." if tested else "")
    elif k == "learn":
        text = f"I'd go deeper on the systems this role centers on, building on what I already do. {body}"
    elif k == "ai":
        tools = (presets or {}).get("ai_tools")
        text = (tools + " " if tools else "") + body
    else:
        text = body
    return text.strip(), pick


def log_review(workspace, job, label, text, fids):
    """Append every drafted answer to workspace/drafts_review.md (what was sent, and from which facts)."""
    p = os.path.join(workspace, "drafts_review.md")
    new = not os.path.exists(p)
    with open(p, "a", encoding="utf-8") as fh:
        if new:
            fh.write("# Drafted answers (sent without waiting; built only from the Fact Bank)\n\n")
        fh.write(f"## {datetime.datetime.now().isoformat(timespec='minutes')} · {job.get('name')}\n"
                 f"**Q:** {' '.join(label.split())[:300]}\n\n**A:** {text}\n\n_facts: {', '.join(fids)}_\n\n")
