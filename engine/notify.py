"""SOS alerts by email, sent from your own mailbox with Python's built-in smtplib (no third-party service).

Configure in .env at the repo root (git-ignored). For Gmail, create an App Password (Google Account > Security >
2-Step Verification > App passwords) and use it here, never your real password:

  REGEN_SMTP_HOST=smtp.gmail.com
  REGEN_SMTP_PORT=465
  REGEN_SMTP_USER=you@gmail.com
  REGEN_SMTP_APP_PASSWORD=xxxx xxxx xxxx xxxx
  REGEN_ALERT_TO=you@gmail.com            # where alerts go (can be an email-to-SMS gateway address)

Not configured -> the alert is appended to workspace/sos_outbox.md so nothing is lost.
`python -m engine sos-test` sends a test alert.
"""
import datetime, os, smtplib, ssl
from email.message import EmailMessage

from engine.config import ROOT, WORKSPACE


def _env():
    env = dict(os.environ)
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.split(" #")[0].strip())
    return env


def sos(subject, body):
    e = _env()
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    os.makedirs(WORKSPACE, exist_ok=True)
    with open(os.path.join(WORKSPACE, "sos_outbox.md"), "a", encoding="utf-8") as fh:  # always keep a local copy
        fh.write(f"\n## {stamp} — {subject}\n{body}\n")
    need = ("REGEN_SMTP_HOST", "REGEN_SMTP_USER", "REGEN_SMTP_APP_PASSWORD", "REGEN_ALERT_TO")
    if not all(e.get(k) for k in need):
        print(f"  ! SOS (email not configured, saved to workspace/sos_outbox.md): {subject}", flush=True)
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, e["REGEN_SMTP_USER"], e["REGEN_ALERT_TO"]
    msg.set_content(f"{body}\n\n— REGEN engine, {stamp}")
    with smtplib.SMTP_SSL(e["REGEN_SMTP_HOST"], int(e.get("REGEN_SMTP_PORT", "465")), context=ssl.create_default_context(), timeout=20) as s:
        s.login(e["REGEN_SMTP_USER"], e["REGEN_SMTP_APP_PASSWORD"])
        s.send_message(msg)
    print(f"  SOS sent: {subject}", flush=True)
    return True
