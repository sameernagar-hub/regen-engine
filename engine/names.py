"""One way to compare company names and roles, used everywhere a "same company" or "same role" decision is made
(selection, per-company caps, in-flight dedupe, requeue, email-code matching).

    company_slug("Acme Robotics, Inc.")  -> "acmerobotics"
    company_slug("acme-robotics")        -> "acmerobotics"    (board tokens and display names meet)
    role_key("Acme, Inc. - Software Engineer  II") -> "acme - software engineer ii"

The display name in events and resumes is never changed; only comparisons go through here.
"""
import re

_SUFFIX = re.compile(r"[,.]?\s+(inc|llc|ltd|corp|corporation|co|gmbh|plc)\.?$", re.I)


def company_slug(name):
    s = _SUFFIX.sub("", (name or "").strip()).lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", s)


def role_key(label, title=None):
    """'<company> - <title>' (or company, title) -> slug + normalized title, for "same role" checks."""
    if title is None:
        company, _, title = (label or "").partition(" - ")
    else:
        company = label
    return f"{company_slug(company)} - {' '.join((title or '').lower().split())}"
