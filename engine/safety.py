"""Airbags: checks that stop the engine, flag a human, and move on.

Every check is cheap and local. When one fires, the current job is NOT submitted. The flag is written to
workspace/flags.jsonl (and events.jsonl), and an SOS email goes out if SMTP is configured (engine/notify.py).

  KILL SWITCH      create workspace/STOP and the runner halts before the next job (delete the file to resume)
  SENSITIVE FIELD  a form asks for SSN, bank/card numbers, passwords, date of birth, driver's license... -> stop
  PAYMENT / FEES   a form field asks for money (application fee, "pay", card) -> stop: real employers don't charge
  RATE CAP         more than REGEN_MAX_PER_DAY submissions (default 25) or 3 per company per day -> stop
  ANSWER DRIFT     a legal answer (sponsorship / authorization / arbitration) differs from what your presets say -> stop
  UNEXPECTED SITE  the form redirected to a domain that isn't the job's ATS -> stop
"""
import datetime, json, os, re
from urllib.parse import urlparse

from engine.config import WORKSPACE

SENSITIVE = re.compile(r"social security|\bssn\b|bank (account|routing)|routing number|credit card|card number|\bcvv\b|"
                       r"password|passcode|date of birth|\bdob\b|birth ?date|driver.?s licen[cs]e|passport number|"
                       r"mother.?s maiden|tax id|\bitin\b|alien (registration )?number|a-number", re.I)
PAYMENT = re.compile(r"application fee|processing fee|pay (now|a fee|to apply)|payment (details|method|information)|"
                     r"enter your card|billing address|gift card|wire transfer", re.I)
ATS_HOSTS = ("greenhouse.io", "ashbyhq.com", "lever.co", "workable.com")


def stop_requested():
    return os.path.exists(os.path.join(WORKSPACE, "STOP"))


def flag(kind, job, detail, url=""):
    """Record an airbag event and send the SOS email (if configured). Returns the flag text."""
    from engine.feedback.events import record
    ev = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "kind": kind, "job": job, "url": url, "detail": detail}
    with open(os.path.join(WORKSPACE, "flags.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    record("flag", **{k: v for k, v in ev.items() if k != "ts"})
    try:
        from engine.notify import sos
        sos(f"[REGEN airbag] {kind}: {job}", f"{detail}\n\n{url}\n\nThe job was NOT submitted. Review it, then re-run or skip.")
    except Exception as e:  # alerts must never crash the engine
        print("  ! SOS email not sent:", e)
    return f"FLAG {kind}: {detail}"


def check_labels(labels):
    """Labels of every field on the form -> list of problems (empty = ok)."""
    out = []
    for l in labels:
        if SENSITIVE.search(l):
            out.append(f"form asks for sensitive data: {' '.join(l.split())[:90]}")
        elif PAYMENT.search(l):
            out.append(f"form asks for payment: {' '.join(l.split())[:90]}")
    return out


def check_page(text, url, job_url):
    # (payment is checked on form labels only: job descriptions at fintechs mention "payment methods" legitimately)
    out = []
    host, job_host = urlparse(url).netloc.lower(), urlparse(job_url).netloc.lower()
    if host and not any(h in host for h in ATS_HOSTS) and host != job_host:
        out.append(f"form is on an unexpected site: {host}")
    return out


def check_rate(company, max_per_day=None, max_per_company=3):
    from engine.feedback.events import read
    max_per_day = max_per_day or int(os.environ.get("REGEN_MAX_PER_DAY", "25"))
    today = datetime.date.today().isoformat()
    subs = [e for e in read("application") if e.get("status") == "SUBMITTED" and not e.get("dry") and e["ts"].startswith(today)]
    out = []
    if len(subs) >= max_per_day:
        out.append(f"daily cap reached ({len(subs)}/{max_per_day}); raise REGEN_MAX_PER_DAY if intended")
    same = [e for e in subs if e.get("job", "").lower().startswith(company.lower())]
    if company and len(same) >= max_per_company:
        out.append(f"{len(same)} submissions to {company} today already")
    return out


LEGAL = [  # question regex -> preset key whose value the answer must equal
    (re.compile(r"without (the need for |requiring |needing )?(current or future )?(visa |employer |employment )?sponsorship", re.I), "authorized_without_sponsorship"),
    (re.compile(r"(require|need).{0,60}sponsor", re.I), "needs_sponsorship_now_or_future"),
    (re.compile(r"authori[sz]ed to work|legally (authori|permitted)", re.I), "work_authorized_us"),
]


def check_answers(answers, presets):
    """answers: [[label, answer], ...] the filler used. A legal answer that disagrees with your presets stops the job."""
    out = []
    for label, ans in answers or []:
        for rx, key in LEGAL:
            if rx.search(label or ""):
                want = presets.get(key)
                if want and ans not in (None, want) and not str(ans).startswith("__"):
                    out.append(f"'{label[:70]}' answered '{ans}' but presets.{key} = '{want}'")
                break  # the first matching legal pattern owns the question (same order as the rules)
    return out
