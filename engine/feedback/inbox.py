"""Outcome loop: read recruiting email, classify it, attach it to the application, and learn from the results.

  python -m engine inbox <messages.json>     messages fetched by an operator (agent reading Gmail in your browser)
  python -m engine inbox --imap [days=3]     read your mailbox directly over IMAP (stdlib imaplib; same .env app
                                             password as engine/notify.py: REGEN_SMTP_USER / REGEN_SMTP_APP_PASSWORD,
                                             REGEN_IMAP_HOST defaults to imap.gmail.com). Read-only: nothing is changed.
  python -m engine learn                     response / OA / interview / rejection rates by lane, ATS and source

messages.json: [{"id": "...", "date": "...", "from": "...", "subject": "...", "snippet": "..."}]
Each classified message becomes an `outcome` event (deduped by id), and workspace/outcomes.md lists them.
Interviews, OAs and offers trigger an alert (engine/notify.py) because they need you quickly.
Anything that looks like a scam (fees, gift cards, crypto, "send your SSN"...) is flagged, never acted on.
"""
import collections, datetime, email, hashlib, imaplib, json, os, re, sys
from email.header import decode_header

from engine.config import WORKSPACE
from engine.feedback.events import read, record

CLASSES = [  # first match wins. Order matters: scam > offer > rejection > OA > interview > action > confirmation
    ("scam", r"gift card|wire (the )?money|western union|bitcoin|crypto(currency)? payment|purchase (your own )?equipment|"
             r"send (us )?your (ssn|social security|bank)|check (will be )?deposit|telegram|whatsapp interview"),
    ("offer", r"offer letter|pleased to offer|extend(ing)? (you )?an offer|offer of employment"),
    ("rejection", r"not (be )?(moving|move) forward|other candidates|not selected|decided not to|regret to inform|"
                  r"position has been filled|no longer (being )?considered|will not be (moving|proceeding)|unfortunately,? (we|after)|"
                  r"(move|moving|go|going) ahead with other|unfortunately,? (have |has )?(decided|chosen)|weren.t selected|"
                  r"high volume of (applicants|applications).{0,40}unfortunately"),  # snippets often stop mid-sentence
    ("oa", r"online assessment|coding (challenge|assessment|test)|hackerrank|codesignal|codility|karat|take-?home|"
           r"assessment invitation|complete the (following )?assessment"),
    # strong signals only: confirmations often say "if selected, we'll reach out to schedule an interview"
    ("interview", r"(invite|inviting) you to (an? )?(interview|call|chat|conversation|phone screen)|calendly\.com|goodtime\.io|"
                  r"(share|send|provide) (us )?your availability|schedule (a|an|your) (call|chat|interview|phone screen|time to)|"
                  r"next round|move you forward|moving you forward|like to (speak|chat|talk) with you"),
    ("action", r"complete your application|action required|verify your email"),
    ("confirmation", r"thanks? (you )?for (applying|your application|your interest|your [\w&.-]+ application)|application (was |has been )?received|"
                     r"we.ve received your application|received your application|^your application (for|to) "),
]
URGENT = {"offer", "interview", "oa", "scam"}


CONDITIONAL = re.compile(r"\b(if|should|in the event|may|will reach out|will be in touch|will contact|we.ll contact)\b", re.I)


def classify(subject, snippet=""):
    text = f"{subject} {snippet}".lower()
    # "If there is a fit, we'll reach out to schedule an interview" is a confirmation, not an invite
    firm = " ".join(s for s in re.split(r"(?<=[.!?])\s+", text) if not CONDITIONAL.search(s))
    for name, rx in CLASSES:
        if re.search(rx, firm if name == "interview" else text):
            return name
    return "other"


def applied_companies():
    """company name (as used in job labels) -> list of application events."""
    out = collections.defaultdict(list)
    for e in read("application"):
        if e.get("status") == "SUBMITTED" and not e.get("dry"):
            out[e["job"].split(" - ")[0].strip()].append(e)
    return out


def match_company(msg, companies):
    hay = f"{msg.get('from', '')} {msg.get('subject', '')} {msg.get('snippet', '')}".lower()
    squashed = re.sub(r"[^a-z0-9]", "", hay)  # "Acme Robotics" vs a board token "acmerobotics"
    best = None
    for co in companies:
        key = re.sub(r"[,.]? (inc|llc|ltd|corp|financial)\.?$", "", co.lower()).strip()
        sq = re.sub(r"[^a-z0-9]", "", key)
        if len(key) >= 3 and (re.search(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])", hay) or (len(sq) >= 6 and sq in squashed)):
            if not best or len(key) > len(best[1]):
                best = (co, key)
    return best[0] if best else None


def ingest(messages):
    seen = {e.get("msg_id") for e in read("outcome")}
    companies = applied_companies()
    new = []
    for m in messages:
        mid = m.get("id") or hashlib.sha1(f"{m.get('date')}{m.get('from')}{m.get('subject')}".encode()).hexdigest()[:16]
        if mid in seen:
            continue
        cls = classify(m.get("subject", ""), m.get("snippet", ""))
        if cls == "other":
            continue
        co = match_company(m, companies)
        if not co and cls not in ("scam",):
            continue  # not about an application we made
        # same company, several roles: keep the application(s) whose title the email mentions
        siblings = [a for k, v in companies.items() if k.split()[0].lower() == co.split()[0].lower() for a in v] if co else []
        text = f"{m.get('subject', '')} {m.get('snippet', '')}".lower()
        def overlap(a):
            words = set(re.findall(r"[a-z]{3,}", a["job"].split(" - ", 1)[-1].lower())) - {"engineer", "software", "the", "and"}
            return sum(1 for w in words if w in text)
        best = max((overlap(a) for a in siblings), default=0)
        apps = [a for a in siblings if overlap(a) == best] if best else companies.get(co, [])
        ev = record("outcome", msg_id=mid, outcome=cls, company=co, subject=m.get("subject", "")[:200],
                    sender=m.get("from", "")[:120], date=m.get("date", ""), jobs=[a["job"] for a in apps],
                    lanes=[a.get("lane") for a in apps])
        new.append(ev)
        if cls in URGENT:
            try:
                from engine.notify import sos
                what = "possible SCAM: do not reply or pay" if cls == "scam" else f"{cls.upper()} — needs you"
                sos(f"[REGEN] {what}: {co or m.get('from', '')}", f"{m.get('subject', '')}\n\n{m.get('snippet', '')}")
            except Exception as e:
                print("  ! alert not sent:", e)
    write_report()
    return new


def write_report():
    evs = read("outcome")
    lines = ["# Outcomes (from your inbox)", "", "| Date | Company | Outcome | Subject |", "|---|---|---|---|"]
    for e in sorted(evs, key=lambda e: e.get("date") or e["ts"], reverse=True):
        lines.append(f"| {str(e.get('date') or e['ts'])[:16]} | {e.get('company') or '?'} | **{e['outcome']}** | {e.get('subject', '')[:80]} |")
    open(os.path.join(WORKSPACE, "outcomes.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def fetch_imap(days=3):
    from engine.notify import _env
    e = _env()
    user, pw = e.get("REGEN_SMTP_USER"), e.get("REGEN_SMTP_APP_PASSWORD")
    if not (user and pw):
        raise SystemExit("IMAP needs REGEN_SMTP_USER and REGEN_SMTP_APP_PASSWORD in .env (see engine/notify.py)")
    M = imaplib.IMAP4_SSL(e.get("REGEN_IMAP_HOST", "imap.gmail.com"))
    M.login(user, pw)
    M.select("INBOX", readonly=True)  # read-only: never marks, moves or deletes anything
    since = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")
    _, data = M.search(None, f'(SINCE "{since}")')
    out = []
    for num in data[0].split()[-400:]:
        _, msg_data = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)] BODY.PEEK[TEXT]<0.1500>)")
        hdr = email.message_from_bytes(msg_data[0][1])
        body = msg_data[1][1].decode("utf-8", "replace") if len(msg_data) > 1 and isinstance(msg_data[1], tuple) else ""
        dec = lambda v: "".join((t.decode(c or "utf-8", "replace") if isinstance(t, bytes) else t) for t, c in decode_header(v or ""))
        out.append({"id": (hdr.get("Message-ID") or "").strip(), "date": hdr.get("Date", ""), "from": dec(hdr.get("From")),
                    "subject": dec(hdr.get("Subject")), "snippet": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))[:600]})
    M.logout()
    return out


def learn():
    """Which lanes / ATSs / sources get responses. The raw signal the memory layer will use to adapt."""
    apps = {}
    for e in read("application"):
        if not e.get("dry"):
            apps[e.get("url") or e["job"]] = e
    subs = [e for e in apps.values() if e["status"] == "SUBMITTED"]
    resumes = {r["job"]: r for r in read("resume")}
    outs = collections.defaultdict(set)
    for o in read("outcome"):
        for j in o.get("jobs", []):
            outs[j].add(o["outcome"])
    def dim(e, k):
        if k == "lane":
            return (resumes.get(e["job"]) or {}).get("lane") or "?"
        if k == "ats":
            u = e.get("url", "")
            return "ashby" if "ashby" in u else "greenhouse" if "greenhouse" in u else "lever" if "lever" in u else "other"
        return "?"
    lines = ["# What's working (auto-generated by `python -m engine learn`)", "",
             f"{len(subs)} submitted applications; outcomes seen for {sum(1 for e in subs if outs.get(e['job']))}.", ""]
    for k in ("lane", "ats"):
        lines += [f"## By {k}", "| " + k + " | applied | any reply | OA | interview | rejection |", "|---|---|---|---|---|---|"]
        groups = collections.defaultdict(list)
        for e in subs:
            groups[dim(e, k)].append(e)
        for g, es in sorted(groups.items()):
            c = lambda name: sum(1 for e in es if name in outs.get(e["job"], set()))
            replied = sum(1 for e in es if outs.get(e["job"], set()) - {"confirmation"})
            lines.append(f"| {g} | {len(es)} | {replied} | {c('oa')} | {c('interview')} | {c('rejection')} |")
        lines.append("")
    text = "\n".join(lines)
    open(os.path.join(WORKSPACE, "learnings.md"), "w", encoding="utf-8").write(text)
    print(text)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--imap":
        msgs = fetch_imap(int(argv[1]) if len(argv) > 1 else 3)
    else:
        msgs = json.load(open(argv[0], encoding="utf-8"))
    new = ingest(msgs)
    for e in new:
        print(f"  {e['outcome']:<12} {e.get('company') or '?':<25} {e.get('subject', '')[:70]}")
    print(f"{len(new)} new outcomes -> events.jsonl, workspace/outcomes.md")
