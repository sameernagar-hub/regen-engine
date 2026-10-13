"""Outreach drafts: a short, truthful note to a recruiter or founder after an application went in.

    python -m engine outreach [days]        -> workspace/outreach/drafts.json (+ .md), newest first

Targets are verified submissions from the last `days` days at employers on the user's tier lists
(profile/priority.json: big tech, AI labs, sponsors) and at startups (Ashby / YC boards). Every sentence is either a
fixed template line or a Fact Bank entry that the *same application's resume* used, so the note can't claim more
than the resume did. Nothing is sent: each draft carries a Gmail compose link the user opens, edits and sends.
Recipients are never guessed (a guessed address is a fabricated fact); the user adds one.
O(E) over the event log, then O(T) drafts.
"""
import datetime, json, os, re, sys
from urllib.parse import quote

from engine.config import WORKSPACE, profile_file

STARTUP_HOSTS = re.compile(r"ashbyhq\.com|ycombinator\.com|workatastartup\.com", re.I)


def _strip(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _bank():
    return json.load(open(profile_file("fact_bank.json"), encoding="utf-8"))


def _links(bank):
    line = dict(bank.get("contact", {})).get("line", "")
    return re.findall(r'href="([^"]+)"', line)


def excluded(company):
    """Employers the domain filter excludes (defense, etc.) never get outreach."""
    from engine.discovery.filters import keep, load_domain
    return keep(load_domain(), "Software Engineer", "", company) == "company excluded"


def lane_facts():
    """lane -> Fact Bank ids ordered by how often that lane's resumes used them (fallback for older applications
    whose resume event predates fact logging). O(E)."""
    import collections
    from engine.feedback.events import read
    c = collections.defaultdict(collections.Counter)
    for e in read("resume"):
        for _, fs in e.get("facts") or []:
            c[e.get("lane")].update(fs)
    return {l: [f for f, _ in cnt.most_common(4)] for l, cnt in c.items()}


def targets(days=7):
    """Verified submissions in the window, with the facts their resume used and why they qualify. O(E)."""
    from engine.discovery.priority import tiers
    from engine.feedback.events import read
    since = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    t = tiers()
    resumes, out = {}, {}
    for e in read():
        if e.get("kind") == "resume" and e.get("url"):
            resumes[e["url"]] = e
        elif (e.get("kind") == "application" and not e.get("dry") and (e.get("ts") or "") >= since
              and (e.get("status") or "").startswith("SUBMITTED") and e.get("proof")):
            co, _, role = (e.get("job") or "").partition(" - ")
            url = e.get("url") or ""
            why = ("tier 1" if t.get("tier1") and t["tier1"].search(co) else
                   "tier 2" if t.get("tier2") and t["tier2"].search(co) else
                   "startup" if STARTUP_HOSTS.search(url) else None)
            if why and not excluded(co):
                r = resumes.get(url, {})
                out[url] = {"company": co.strip(), "role": role.strip(), "url": url, "ts": e["ts"], "why": why,
                            "lane": r.get("lane"), "facts": [f for _, fs in (r.get("facts") or []) for f in fs]}
    return sorted(out.values(), key=lambda x: ({"tier 1": 0, "tier 2": 1, "startup": 2}[x["why"]], x["ts"]), reverse=False)


def draft(t, bank=None):
    """One note from template lines + the first two Fact Bank entries this application's resume used."""
    bank = bank or _bank()
    name = dict(bank.get("contact", {})).get("name", "").title()
    facts = bank.get("facts", {})
    lines = [_strip(facts[f]) for f in t["facts"] if f in facts][:2]
    links = _links(bank)
    subject = f"{t['role']} application: {name}"
    body = "\n".join([
        "Hi,",
        "",
        f"I just applied for the {t['role']} role at {t['company']} and wanted to reach out directly.",
        *(["", "Two things from my background that match the role:"] + [f"- {l}" for l in lines] if lines else []),
        "",
        *([" | ".join(links), ""] if links else []),
        "I'd be glad to talk or work through a technical screen whenever it suits you.",
        "",
        "Thanks,",
        name,
    ])
    compose = f"https://mail.google.com/mail/?view=cm&fs=1&su={quote(subject)}&body={quote(body)}"
    return dict(t, subject=subject, body=body, compose=compose, sources=t["facts"][:2])


def build(days=7):
    bank = _bank()
    lf = lane_facts()
    ts = targets(days)
    for t in ts:
        if not t["facts"]:
            t["facts"] = lf.get(t["lane"]) or lf.get("fullstack") or []
            t["facts_from"] = "lane"  # the lane's most-used facts: still Fact Bank only
    drafts = [draft(t, bank) for t in ts]
    d = os.path.join(WORKSPACE, "outreach")
    os.makedirs(d, exist_ok=True)
    json.dump(drafts, open(os.path.join(d, "drafts.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    with open(os.path.join(d, "drafts.md"), "w", encoding="utf-8") as f:
        f.write(f"# Outreach drafts ({datetime.date.today()}): nothing sent; open each compose link, add a recipient, send\n\n")
        for x in drafts:
            f.write(f"## {x['company']}: {x['role']} ({x['why']})\nFacts: {', '.join(x['sources']) or '-'}\n\n"
                    f"**{x['subject']}**\n\n{x['body']}\n\n[Open in Gmail]({x['compose']})\n\n---\n\n")
    return drafts


SOFTWARE_POST = re.compile(r"engineer|developer|\bswe\b|full.?stack|back.?end|front.?end|platform|infrastructure|"
                           r"\bsre\b|devops|\bml\b|machine learning|\bai\b|llm|data", re.I)
NOT_A_FIT = re.compile(r"sales|go.to.market|marketing|product manager|\bpm\b|head of|director|vp\b|principal|distinguished|"
                       r"staff|manager|scientist|£|€|/hr\b", re.I)
NOT_FOR_YOU = re.compile(r"citizen(ship)? (required|only)|clearance|no (visa )?sponsorship|onsite in (london|berlin|paris|"
                         r"toronto|amsterdam)|dutch required|german required|(eu|uk|canada) only", re.I)


def hn_targets(limit=60):
    """Published HN hiring contacts (engine/discovery/hn.py) for software roles in the US or remote, minus employers
    the domain filter excludes and posts that rule the candidate out (citizenship, no sponsorship, non-US only). O(C)."""
    p = os.path.join(WORKSPACE, "outreach", "hn_contacts.json")
    if not os.path.exists(p):
        return []
    from engine.tailoring.batch import load_lanes, route
    from engine.discovery.filters import keep, load_domain
    cfg, lf, dom = load_lanes(), lane_facts(), load_domain()
    out = []
    for c in json.load(open(p, encoding="utf-8")):
        parts = [x.strip() for x in c["post"].split("|")]
        roles = next((x for x in parts[1:] if SOFTWARE_POST.search(x)), "")
        if not c.get("us") or not roles or NOT_FOR_YOU.search(c["post"]) or excluded(c["company"]):
            continue
        if keep(dom, roles, "", c["company"]) or NOT_A_FIT.search(roles):
            continue  # the same title filter as applications: no sales/PM/marketing, no principal/distinguished
        lane = route(cfg, roles, c["post"])
        out.append({"company": c["company"], "role": roles[:90], "to": c["email"], "url": c["hn"], "ts": "",
                    "why": "HN hiring post", "lane": lane, "facts": lf.get(lane) or lf.get("fullstack") or []})
    return out[:limit]


def hn_draft(t, bank=None):
    """Cold note to a founder who posted on HN: their own post is the reason to write, two Fact Bank lines are the
    evidence. Addressed to the contact they published; still nothing is sent."""
    bank = bank or _bank()
    name = dict(bank.get("contact", {})).get("name", "").title()
    facts = bank.get("facts", {})
    lines = [_strip(facts[f]) for f in t["facts"] if f in facts][:2]
    links = _links(bank)
    subject = f"Re: your HN hiring post ({t['role'][:60]})"
    body = "\n".join([
        "Hi,",
        "",
        f"I saw the {t['company']} post in HN's Who is hiring thread ({t['role']}) and wanted to reach out.",
        *(["", "Two things from my background that fit:"] + [f"- {l}" for l in lines] if lines else []),
        "",
        *([" | ".join(links), ""] if links else []),
        "I'm happy to send my resume, and I'd be glad to talk or do a technical screen.",
        "",
        "Thanks,",
        name,
    ])
    compose = f"https://mail.google.com/mail/?view=cm&fs=1&to={quote(t['to'])}&su={quote(subject)}&body={quote(body)}"
    return dict(t, subject=subject, body=body, compose=compose, sources=t["facts"][:2])


def gmail_drafts(drafts, blocked=None):
    """Save drafts into the user's Gmail Drafts folder over IMAP (the app password in .env). APPEND only: nothing is
    sent, read or changed; the user reviews and sends each one. Every subject + body passes the leak guard first
    (engine/guard.py: secrets, phone, address, salary, visa/work-authorization status): a draft that fails is not
    saved, a `flag` event names the rule, and it lands in `blocked` as (company, rules). Returns how many were saved."""
    import email.message, email.utils, imaplib, time as T
    from engine import guard
    from engine.feedback.events import record
    from engine.notify import _env
    blocked = [] if blocked is None else blocked
    ok = []
    for d in drafts:
        if not d.get("to"):
            continue  # a draft without a published recipient stays a compose link
        rules = guard.outreach_problems(d.get("subject", "") + "\n" + d.get("body", ""))
        if rules:
            blocked.append((d.get("company", "?"), rules))
            record("flag", flag_kind="outreach_guard", job=d.get("company", "?"), detail="; ".join(rules))
        else:
            ok.append(d)
    if not ok:
        return 0
    e = _env()
    user, pw = e.get("REGEN_SMTP_USER"), (e.get("REGEN_SMTP_APP_PASSWORD") or "").replace(" ", "")
    if not (user and pw):
        raise SystemExit("needs REGEN_SMTP_USER and REGEN_SMTP_APP_PASSWORD in .env")
    M = imaplib.IMAP4_SSL(e.get("REGEN_IMAP_HOST", "imap.gmail.com"))
    M.login(user, pw)
    n = 0
    for d in ok:
        m = email.message.EmailMessage()
        m["From"], m["To"], m["Subject"] = user, d["to"], d["subject"]
        m["Date"] = email.utils.formatdate(localtime=True)
        m.set_content(d["body"])
        typ, _ = M.append('"[Gmail]/Drafts"', "\\Draft", imaplib.Time2Internaldate(T.time()), m.as_bytes())
        n += typ == "OK"
    M.logout()
    return n


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "hn":  # python -m engine outreach hn [limit] [--gmail]
        bank = _bank()
        ds = [hn_draft(t, bank) for t in hn_targets(int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 60)]
        d = os.path.join(WORKSPACE, "outreach")
        os.makedirs(d, exist_ok=True)
        json.dump(ds, open(os.path.join(d, "hn_drafts.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        for x in ds:
            print(f"  {x['company'][:28]:<28} {x['to']:<34} {x['role'][:40]}")
        blocked = []
        saved = gmail_drafts(ds, blocked) if "--gmail" in argv else 0
        for co, rules in blocked:
            print(f"  blocked by the leak guard: {co[:28]} ({'; '.join(rules)})")
        print(f"{len(ds)} HN drafts -> workspace/outreach/hn_drafts.json" + (f"; {saved} saved to Gmail Drafts (nothing sent)" if saved else " (nothing sent)"))
        return
    ds = build(int(argv[0]) if argv else 7)
    for x in ds:
        print(f"  {x['why']:<8} {x['company'][:24]:<24} {x['role'][:50]}")
    print(f"{len(ds)} drafts -> workspace/outreach/drafts.json (nothing sent)")


if __name__ == "__main__":
    main()
