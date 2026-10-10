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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ds = build(int(argv[0]) if argv else 7)
    for x in ds:
        print(f"  {x['why']:<8} {x['company'][:24]:<24} {x['role'][:50]}")
    print(f"{len(ds)} drafts -> workspace/outreach/drafts.json (nothing sent)")


if __name__ == "__main__":
    main()
