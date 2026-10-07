"""`python -m engine alerts <file>`: job-alert emails (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Handshake) as a lead source.

The aggregators hide the employer's own posting behind their apply flows, so each listing is a *lead*, exactly like a
newgrad-jobs row: it passes the domain filter, then newgrad.resolve() looks the company up on its own Greenhouse /
Ashby / Lever / Workable board and matches the title there.
  resolved   -> workspace/queue.json (apply at the source; the board is added to boards.json for future scans)
  unresolved -> workspace/alert_leads.json (merged across runs, never overwritten; Workday/iCIMS/custom portals)

Input is what engine/discovery/gmail_alerts.js writes into the Gmail page: rows split by '§', fields by '¦'
(source ¦ title ¦ company ¦ location ¦ email date). Plain tab-separated lines work too.
Only listing text is used; no links, tracking ids or message bodies are stored.
"""
import json, os, re, sys
from datetime import datetime, timezone

from engine.config import WORKSPACE
from engine.discovery.filters import load_domain, keep, norm, applied_keys
from engine.discovery.newgrad import resolve
from engine.discovery.scan import filter_jobs, merge_queue
from engine.feedback.events import record

BADGE = re.compile(r"^(new|actively recruiting|easy apply|manage alerts|view details|1-click apply)$", re.I)
NOT_COMPANY = re.compile(r"^(your job listings|you can edit|to help refine)", re.I)
STAFFING = re.compile(r"\b(recruit\w*|staffing|talent\w*|consult\w*|cybercoders|insight global|appleone|pridestaff|lhh|"
                      r"express employment|yoh|jobs for good|wiraa|talenthop|dataannotation|fonzi)\b", re.I)


def parse(text):
    """Rows of {source, title, company, location, date}; badge/header mis-parses are dropped, not guessed at."""
    rows = []
    chunks = text.split("§") if "§" in text else text.splitlines()
    for c in chunks:
        f = [x.strip() for x in (c.split("¦") if "¦" in c else c.split("\t"))]
        if len(f) < 4 or f[0] in ("REGEN-ALERTS", "END-ALERTS"):
            continue
        src, title, company, loc = f[:4]
        if not title or not company or BADGE.match(title) or NOT_COMPANY.match(company):
            continue
        loc = re.sub(r"\s*\((on-?site|onsite|hybrid)\)$", "", loc, flags=re.I)
        loc = loc.replace("San Francisco Bay Area", "San Francisco, CA")
        rows.append(dict(source=src, title=title, company=company.strip(" ,"), location=loc,
                         date=f[4] if len(f) > 4 else ""))
    return rows


def leads_from(rows, dom=None):
    """Domain filter + de-dupe against everything already applied to. Staffing agencies and AI-trainer gig boards are
    dropped: they repost other employers' jobs (no ATS of their own to resolve) or aren't engineering roles."""
    dom = dom or load_domain()
    _, keys = applied_keys()
    leads, dropped, seen = [], {}, set()
    for r in rows:
        why = keep(dom, r["title"], r["location"], r["company"])
        if not why and STAFFING.search(r["company"]):
            why = "staffing/aggregator"
        if not why and norm(f"{r['company']} - {r['title']}") in keys:
            why = "already applied"
        k = (norm(r["company"]), norm(r["title"]))
        if not why and k in seen:
            why = "duplicate"
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        seen.add(k)
        leads.append(dict(company=r["company"], title=r["title"], location=r["location"], date=r["date"],
                          via=r["source"], h1b=None, lead_url=None))
    return leads, dropped


def save_unresolved(unresolved, path=None):
    path = path or os.path.join(WORKSPACE, "alert_leads.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    by = {(norm(l["company"]), norm(l["title"])): l for l in old}
    today = datetime.now(timezone.utc).date().isoformat()
    for l in unresolved:
        by.setdefault((norm(l["company"]), norm(l["title"])), {**l, "first_seen": today})
    json.dump(list(by.values()), open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return len(by)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: python -m engine alerts <workspace/alerts/YYYY-MM-DD.txt>")
        return
    rows = parse(open(argv[0], encoding="utf-8").read())
    leads, dropped = leads_from(rows)
    resolved, unresolved = resolve(leads, source="email-alert")
    now = datetime.now(timezone.utc).isoformat()
    fresh, d2 = filter_jobs([{**j, "posted": j.get("posted") or now} for j in resolved], 3650)
    for k, v in d2.items():
        dropped[k] = dropped.get(k, 0) + v
    q = merge_queue(fresh)
    total = save_unresolved(unresolved)
    for j in fresh:
        record("discovered", job=f"{j['company']} - {j['title']}", url=j.get("url"), ats=j["ats"], source="email-alert")
        print(f"{j['id']} | {j['ats'][:2]} | {j['company'][:22]} | {j['title'][:60]} | {j['location'][:30]}")
    record("alerts", listings=len(rows), leads=len(leads), resolved=len(fresh), unresolved=len(unresolved), dropped=dropped)
    print(f"{len(rows)} listings -> {len(leads)} leads: {len(fresh)} resolved to an ATS -> queue.json ({len(q)} total), "
          f"{len(unresolved)} unresolved -> alert_leads.json ({total} kept); dropped {dropped}")


if __name__ == "__main__":
    main()
