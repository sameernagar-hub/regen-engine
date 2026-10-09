"""Match Greenhouse security codes to the jobs waiting for them.

  python -m engine codes '<json from engine/discovery/gmail_codes.js>'

Each waiting job has workspace/codes/<board>_<id>.wait (first line: "Company - Role", second: the form URL).
A code is written to <board>_<id>.txt only when the email names that same company (normalized compare), so a
code is never typed into another company's form. Several codes for one company: the newest (first row) wins.
Already-answered or stale codes are left alone. O(waiting x codes), both tiny.
"""
import datetime, json, os, re, sys

from engine.config import WORKSPACE


def _norm(s):
    s = re.sub(r"[,.]?\s+(inc|llc|ltd|corp|corporation|co)\.?$", "", (s or "").strip(), flags=re.I)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def waiting(workspace=None):
    d = os.path.join(workspace or WORKSPACE, "codes")
    out = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".wait") and not os.path.exists(os.path.join(d, f[:-5] + ".txt")):
                first = open(os.path.join(d, f), encoding="utf-8").read().splitlines()[:1]
                out.append((f[:-5], (first[0] if first else "").split(" - ")[0]))
    return out


def fresh(code, since, today=None):
    """Was this code sent after the job started waiting? Gmail shows "22:17" for today and "Oct 6" for older mail.
    No time given -> accepted (the caller vouched for it). A three-minute margin covers clock rounding and round-robin delay before .wait is written."""
    when = (code.get("when") or "").strip()
    if not when:
        return True
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?:\s*([AaPp][Mm]))?", when)
    if not m:
        return False  # a date, not a time: older than today
    h, mi = int(m.group(1)), int(m.group(2))
    if m.group(3):
        h = h % 12 + (12 if m.group(3).lower() == "pm" else 0)
    today = today or datetime.date.today()
    sent = datetime.datetime.combine(today, datetime.time(h, mi))
    return sent >= datetime.datetime.fromtimestamp(since) - datetime.timedelta(minutes=3)  # round-robin: the email can land before the tab writes .wait


def match(codes, workspace=None):
    """codes: [{"company", "code", "when"?}] newest first -> {slug: code} written to disk."""
    d = os.path.join(workspace or WORKSPACE, "codes")
    written = {}
    for slug, company in waiting(workspace):
        want = _norm(company) or _norm(slug.split("_")[0])
        since = os.path.getmtime(os.path.join(d, slug + ".wait"))
        hit = next((c for c in codes if _norm(c.get("company")) == want and re.fullmatch(r"[A-Za-z0-9]{8}", c.get("code", ""))
                    and fresh(c, since)), None)
        if hit:
            open(os.path.join(d, slug + ".txt"), "w").write(hit["code"])
            written[slug] = hit["code"]
    return written


CODE_RX = re.compile(r"application to ([^,]+?)(?: - |, ).*?application:?\s*([A-Za-z0-9]{8})\b", re.I | re.S)


def imap_codes(M):
    """Security-code emails from today, newest first, as [{company, code, when}] (read-only, headers + 1.5 KB of body)."""
    import email, email.utils
    since = datetime.date.today().strftime("%d-%b-%Y")
    _, data = M.search(None, f'(SINCE "{since}" SUBJECT "security code")')
    out = []
    for num in reversed(data[0].split()[-30:]):
        _, md = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)] BODY.PEEK[TEXT]<0.1500>)")
        hdr = email.message_from_bytes(md[0][1])
        body = md[1][1].decode("utf-8", "replace") if len(md) > 1 and isinstance(md[1], tuple) else ""
        m = CODE_RX.search(" ".join((str(hdr.get("Subject", "")) + " " + re.sub(r"<[^>]+>", " ", body)).split()))
        if m:
            sent = email.utils.parsedate_to_datetime(hdr["Date"]).astimezone()
            out.append({"company": m.group(1).strip(), "code": m.group(2), "when": sent.strftime("%H:%M")})
    return out


def watch(every=8, idle_exit=0):
    """Hands-free: poll the mailbox over IMAP while any job waits for a code; write each code as it lands.
    Needs REGEN_SMTP_USER + REGEN_SMTP_APP_PASSWORD in .env (a Gmail app password). Read-only (never marks or moves).
    One IMAP login, one SEARCH per poll and only while something waits: O(waiting x codes) per poll, both tiny."""
    import imaplib, time
    from engine.notify import _env
    e = _env()
    user, pw = e.get("REGEN_SMTP_USER"), e.get("REGEN_SMTP_APP_PASSWORD")
    if not (user and pw):
        raise SystemExit("codes --watch needs REGEN_SMTP_USER and REGEN_SMTP_APP_PASSWORD (Gmail app password) in .env")
    M = imaplib.IMAP4_SSL(e.get("REGEN_IMAP_HOST", "imap.gmail.com"))
    M.login(user, pw)
    idle = 0
    try:
        while True:
            if waiting():
                idle = 0
                M.select("INBOX", readonly=True)
                w = match(imap_codes(M))
                if w:
                    print(f"{datetime.datetime.now():%H:%M:%S} codes written: {', '.join(w)}", flush=True)
            else:
                idle += every
                if idle_exit and idle >= idle_exit:
                    return
            time.sleep(every)
    finally:
        M.logout()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--watch":
        return watch(idle_exit=int(argv[1]) if len(argv) > 1 else 0)
    raw = argv[0] if argv else sys.stdin.read()
    codes = json.loads(open(raw).read() if os.path.exists(raw) else raw)
    w = match(codes)
    left = [s for s, _ in waiting()]
    print(f"{len(w)} code(s) written: {', '.join(w) or '-'}; still waiting: {', '.join(left) or '-'}")
