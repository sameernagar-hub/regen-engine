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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    raw = argv[0] if argv else sys.stdin.read()
    codes = json.loads(open(raw).read() if os.path.exists(raw) else raw)
    w = match(codes)
    left = [s for s, _ in waiting()]
    print(f"{len(w)} code(s) written: {', '.join(w) or '-'}; still waiting: {', '.join(left) or '-'}")
