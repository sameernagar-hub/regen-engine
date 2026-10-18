"""Match Greenhouse security codes to the jobs waiting for them.

  python -m engine codes '<json from engine/discovery/gmail_codes.js>'

Each waiting job has workspace/codes/<board>_<id>.wait (first line: "Company - Role", second: the form URL).
A code is written to <board>_<id>.txt only when the email names that same company (normalized compare), so a
code is never typed into another company's form. Several codes for one company: oldest waiter gets the oldest unused code; a bounced code is never reused for that job.
Already-answered or stale codes are left alone. O(waiting x codes), both tiny.
"""
import datetime, json, os, re, sys, time

from engine.config import WORKSPACE


def _norm(s):
    from engine.names import company_slug  # one company comparison everywhere
    return company_slug(s)


def waiting(workspace=None):
    d = os.path.join(workspace or WORKSPACE, "codes")
    out = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".wait") and not os.path.exists(os.path.join(d, f[:-5] + ".txt")):
                first = open(os.path.join(d, f), encoding="utf-8", errors="replace").read().splitlines()[:1]
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
    # oldest waiter first; each code goes to one job only, and a job never gets a code it already bounced
    # (two applications to one company wait at once: Gmail may thread both codes, so the order alone can't be trusted)
    for slug, company in sorted(waiting(workspace), key=lambda w: os.path.getmtime(os.path.join(d, w[0] + ".wait"))):
        want = _norm(company) or _norm(slug.split("_")[0])
        tried_f = os.path.join(d, slug + ".tried")
        tried = set(open(tried_f).read().split()) if os.path.exists(tried_f) else set()
        since = os.path.getmtime(os.path.join(d, slug + ".wait"))
        if tried:
            since -= 600  # a re-wait after a bounced code: the right code arrived before this .wait was rewritten
        hit = next((c for c in reversed(codes) if _norm(c.get("company")) == want and re.fullmatch(r"[A-Za-z0-9]{8}", c.get("code", ""))
                    and c["code"] not in tried and c["code"] not in written.values() and fresh(c, since)), None)
        if hit:
            open(os.path.join(d, slug + ".txt"), "w").write(hit["code"])
            open(tried_f, "a").write(hit["code"] + "\n")
            written[slug] = hit["code"]
            try:  # benchmark B6: how long the form waited for its code (never the code itself)
                from engine.feedback.events import record
                record("code", slug=slug, latency_s=round(time.time() - os.path.getmtime(os.path.join(d, slug + ".wait"))))
            except Exception:
                pass
    return written


CODE_RX = re.compile(r"application to ([^,]+?)(?: - |, ).*?application:?\s*([A-Za-z0-9]{8})\b", re.I | re.S)


def imap_codes(M):
    """Security-code emails from today, newest first, as [{company, code, when}] (read-only: BODY.PEEK never marks
    mail read). Each message is fetched whole and decoded (10-11: the first 1.5 KB of the quoted-printable HTML held
    only <head>, and Gmail returns the parts in its own order, so no code was ever found)."""
    import email, email.utils
    since = datetime.date.today().strftime("%d-%b-%Y")
    _, data = M.search(None, f'(SINCE "{since}" SUBJECT "security code")')
    out = []
    for num in reversed(data[0].split()[-30:]):
        _, md = M.fetch(num, "(BODY.PEEK[])")
        raw = next((x[1] for x in md if isinstance(x, tuple)), b"")
        msg = email.message_from_bytes(raw)
        parts = [msg] if not msg.is_multipart() else [p for p in msg.walk() if p.get_content_maintype() == "text"]
        body = " ".join((p.get_payload(decode=True) or b"").decode(p.get_content_charset() or "utf-8", "replace") for p in parts)
        co = re.search(r"application to (.+?)\s*$", " ".join(str(msg.get("Subject", "")).split()), re.I)
        code = re.search(r"application:?\s*([A-Za-z0-9]{8})\b", " ".join(re.sub(r"<[^>]+>", " ", body).split()), re.I)
        if co and code and msg.get("Date"):
            sent = email.utils.parsedate_to_datetime(msg["Date"]).astimezone()
            out.append({"company": co.group(1).strip(), "code": code.group(1), "when": sent.strftime("%H:%M")})
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
    M.login(user, pw.replace(" ", ""))  # Google shows app passwords as "abcd efgh ijkl mnop"
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
                if idle % 240 < every:  # Gmail drops an idle connection; 10-17 the first select after a quiet spell
                    M.noop()            # failed (EOF) while a job waited on its code. A NOOP every ~4 min keeps it.
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
