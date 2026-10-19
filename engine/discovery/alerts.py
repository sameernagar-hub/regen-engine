"""`python -m engine alerts <file>`: job-alert emails (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Handshake) as a lead source.

The aggregators hide the employer's own posting behind their apply flows, so each listing is a *lead*, exactly like a
newgrad-jobs row: it passes the domain filter, then newgrad.resolve() looks the company up on its own Greenhouse /
Ashby / Lever / Workable board and matches the title there.
  resolved   -> workspace/queue.json (apply at the source; the board is added to boards.json for future scans)
  unresolved -> workspace/alert_leads.json (merged across runs, never overwritten; Workday/iCIMS/custom portals)

Input is what engine/discovery/gmail_alerts.js writes into the Gmail page: rows split by '§', fields by '¦'
(source ¦ title ¦ company ¦ location ¦ email date). Plain tab-separated lines work too.

`python -m engine alerts --imap [days=2]` (v0.13) reads LinkedIn alert mail straight over IMAP with the same Gmail
app password the code watcher uses: no browser tab. Only the text/plain part is read; each card is the three lines
(title, company, location) above its "View job:" link. Message ids already read are kept in
workspace/alerts_imap_seen.json, so a pass fetches only new mail (1 search + 1 fetch per new message).
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


NOISE = re.compile(r"^(\d+ (school )?alumni|\d+ connections?|actively recruiting|easy apply|promoted|be an early applicant|"
                   r"apply with resume.*|new|top applicant|.*\$\d.*|see all jobs.*|-+)$", re.I)


def linkedin_cards(text, date=""):
    """Rows from one LinkedIn alert's text/plain body: the last three non-noise lines before each "View job:" link,
    after the previous card's separator. Cards that don't have exactly title/company/location are skipped. O(len)."""
    rows = []
    for chunk in re.split(r"View job:\s*\S+", text)[:-1]:
        lines = [l.strip() for l in chunk.splitlines()]
        lines = [l for l in lines if l and not NOISE.match(l) and not l.startswith("http") and "job alert" not in l.lower()]
        if len(lines) >= 3:
            title, company, loc = lines[-3:]
            rows.append(dict(source="linkedin", title=title, company=company.strip(" ,"), location=loc, date=date))
    return rows


def imap_rows(days=2):
    """LinkedIn alert cards from mail of the last `days` days that was not read before. Read-only mailbox."""
    import email, imaplib
    from datetime import timedelta
    from engine.notify import _env
    e = _env()
    if not (e.get("REGEN_SMTP_USER") and e.get("REGEN_SMTP_APP_PASSWORD")):
        raise SystemExit("alerts --imap needs REGEN_SMTP_USER + REGEN_SMTP_APP_PASSWORD in .env")
    seen_p = os.path.join(WORKSPACE, "alerts_imap_seen.json")
    try:
        seen = set(json.load(open(seen_p, encoding="utf-8")))
    except (OSError, ValueError):
        seen = set()
    M = imaplib.IMAP4_SSL(e.get("REGEN_IMAP_HOST", "imap.gmail.com"))
    M.login(e["REGEN_SMTP_USER"], e["REGEN_SMTP_APP_PASSWORD"])
    M.select('"[Gmail]/All Mail"', readonly=True)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
    _, data = M.search(None, f'(SINCE {since} FROM "linkedin.com" BODY "View job:")')
    rows, read = [], 0
    for i in data[0].split():
        _, d = M.fetch(i, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID DATE)])")
        h = email.message_from_bytes(d[0][1])
        mid = h.get("Message-ID", "").strip() or i.decode()
        if mid in seen:
            continue
        _, d = M.fetch(i, "(BODY.PEEK[])")
        m = email.message_from_bytes(d[0][1])
        for part in m.walk():
            if part.get_content_type() == "text/plain":
                text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
                rows += linkedin_cards(text, h.get("Date", "")[:16])
                break
        seen.add(mid); read += 1
    M.logout()
    tmp = seen_p + ".tmp"
    json.dump(sorted(seen)[-5000:], open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, seen_p)
    print(f"alerts --imap: {read} new alert emails, {len(rows)} listings")
    return rows


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: python -m engine alerts <workspace/alerts/YYYY-MM-DD.txt> | --imap [days]")
        return
    if argv[0] == "--imap":
        rows = imap_rows(float(argv[1]) if len(argv) > 1 else 2)
    else:
        rows = parse(open(argv[0], encoding="utf-8").read())
    leads, dropped = leads_from(rows)
    resolved, unresolved = resolve(leads, source="email-alert")
    now = datetime.now(timezone.utc).isoformat()
    fresh, d2 = filter_jobs([{**j, "posted": j.get("posted") or now} for j in resolved], 3650)
    for k, v in d2.items():
        dropped[k] = dropped.get(k, 0) + v
    q = merge_queue(fresh, log=False)
    total = save_unresolved(unresolved)
    for j in fresh:
        record("discovered", job=f"{j['company']} - {j['title']}", url=j.get("url"), ats=j["ats"], source="email-alert")
        print(f"{j['id']} | {j['ats'][:2]} | {j['company'][:22]} | {j['title'][:60]} | {j['location'][:30]}")
    record("alerts", listings=len(rows), leads=len(leads), resolved=len(fresh), unresolved=len(unresolved), dropped=dropped)
    print(f"{len(rows)} listings -> {len(leads)} leads: {len(fresh)} resolved to an ATS -> queue.json ({len(q)} total), "
          f"{len(unresolved)} unresolved -> alert_leads.json ({total} kept); dropped {dropped}")


if __name__ == "__main__":
    main()
