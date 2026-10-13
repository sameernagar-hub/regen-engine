"""Leak guard rules, shared by the supervisor's file scan and the outreach Gmail path.

Two rule sets:
  secret_rule(text)       secret values from .env (app password, tokens) and secret shapes (API keys, private keys,
                          SSN shape). Applies to everything the engine writes: logs, ledger files, specs, resumes.
  outreach_problems(text) secret_rule + data the user gave the engine for forms only: phone, street address,
                          visa / work-authorization status, salary numbers. A cold email never carries them unless
                          the preset key is listed in presets["_outreach_allowed"] (the user's call, not Claude's).

Rule names are returned, never the matched value: the audit trail must not become the leak.
"""
import json, re

SECRET_RX = [
    re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|xox[abp]-[A-Za-z0-9-]{20,}|AIza[0-9A-Za-z_-]{30,})"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN shape
]
# status words a recruiter note has no reason to contain (the application form already answered them)
STATUS_RX = re.compile(r"\b(H-?1B|green card|sponsorship|visa|work authori[sz]ation|work permit)\b", re.I)
STATUS_CASED_RX = re.compile(r"\b(CPT|EAD|OPT|F-1)\b")  # cased: "opt-in" and an F1 score are not statuses
PRIVATE_KEYS = ("phone", "address_line1", "salary_expectation", "market_salary")
STATUS_KEYS = ("visa", "f1_status", "work_auth_status", "on_opt", "held_h1b", "needs_sponsorship_now_or_future")


def secrets():
    """[(env key, value)] for secret-looking keys in .env, spaces stripped (Gmail shows app passwords in groups)."""
    from engine.notify import _env
    e = _env()
    return [(k, v.replace(" ", "")) for k, v in e.items()
            if re.search(r"PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE", k) and len((v or "").replace(" ", "")) >= 8]


def secret_rule(text, _secrets=None):
    """Name of the first secret rule `text` breaks, or None."""
    flat = text.replace(" ", "")
    return next((k for k, v in (secrets() if _secrets is None else _secrets) if v in flat), None) or \
        next((f"pattern {i}" for i, rx in enumerate(SECRET_RX) if rx.search(text)), None)


def _presets():
    from engine.config import profile_file
    try:
        return json.load(open(profile_file("presets.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _phone_rx(phone):
    d = re.sub(r"\D", "", str(phone))[-7:]
    return re.compile(r"[\s().-]*".join(d)) if len(d) == 7 else None


def outreach_problems(text, presets=None, _secrets=None):
    """Rule names a cold-email body breaks (empty list = OK to save as a draft)."""
    p = _presets() if presets is None else presets
    allowed = set(p.get("_outreach_allowed") or [])
    out = []
    rule = secret_rule(text, _secrets)
    if rule:
        out.append(f"secret ({rule})")
    if "phone" not in allowed and p.get("phone") and (rx := _phone_rx(p["phone"])) and rx.search(text):
        out.append("preset phone")
    addr = str(p.get("address_line1") or "").strip()
    if "address_line1" not in allowed and len(addr) >= 6 and addr.lower() in text.lower():
        out.append("preset address_line1")
    for k in ("salary_expectation", "market_salary"):
        v = re.sub(r"\D", "", str(p.get(k) or ""))
        if k not in allowed and len(v) >= 5 and v in re.sub(r"[,$\s]", "", text):
            out.append(f"preset {k}")
    if not allowed.intersection(STATUS_KEYS) and (m := STATUS_RX.search(text) or STATUS_CASED_RX.search(text)):
        out.append(f"work-authorization status ({m.group(0).lower()})")
    return out


def pdf_text(path):
    """Text of a PDF (the same pypdf read-back the composer uses), '' when unreadable."""
    try:
        from pypdf import PdfReader
        return "\n".join(pg.extract_text() or "" for pg in PdfReader(path).pages)
    except Exception:
        return ""
