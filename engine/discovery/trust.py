"""Trust gate: is this a real employer and a real job, before any personal data is shared?

Job scams copy real postings, live on look-alike domains, and ask for money, bank details or chat-app interviews.
The engine only auto-fills forms hosted by an applicant-tracking system the employer itself controls (its own
Greenhouse / Lever / Ashby / Workable board), and every job description passes this check first:

  verdict(url, jd, company) -> (ok, reasons)

Signals (no network calls; the posting is already on disk):
  host       the application URL must be a known ATS host or the employer's own careers domain; anything else
             (shorteners, form builders, free web hosts, chat apps) is never auto-filled
  red flags  phrases seen in job-scam reports: up-front payments, buying equipment with a check you are sent,
             interviews over chat apps, crypto/gift-card pay, asking for SSN / bank details before an offer,
             "no experience, $50/hr, data entry", reshipping / package forwarding
  contact    a posting that says to apply by emailing a free-mail address (gmail, outlook, yahoo...)

Complexity: one regex pass over the description, O(len(jd)). Inbox messages use `message_flags` (engine/feedback/inbox.py).
"""
import html, re
from urllib.parse import urlparse

ATS_HOSTS = re.compile(r"(^|\.)(greenhouse\.io|ashbyhq\.com|lever\.co|workable\.com|myworkdayjobs\.com|icims\.com|smartrecruiters\.com|"
                       r"jobvite\.com|bamboohr\.com|rippling\.com|dover\.com|ycombinator\.com|workatastartup\.com)$", re.I)
NEVER_HOSTS = re.compile(r"(^|\.)(bit\.ly|tinyurl\.com|t\.me|telegram\.(me|org)|wa\.me|whatsapp\.com|forms\.gle|docs\.google\.com|"
                         r"typeform\.com|jotform\.com|wixsite\.com|weebly\.com|blogspot\.com|sites\.google\.com|linktr\.ee|"
                         r"carrd\.co|000webhostapp\.com|netlify\.app|github\.io)$", re.I)
FREE_MAIL = r"gmail|googlemail|outlook|hotmail|live|yahoo|aol|proton(mail)?|icloud|gmx|mail|yandex|zoho"

RED_FLAGS = [
    ("pay to apply", r"(application|registration|training|onboarding|background check|processing) fee|pay (for|a fee for) (your )?(training|equipment|background)"),
    ("equipment check", r"(we|company) will (send|mail) you a (check|cheque)|purchase (your )?(equipment|laptop|software) (from|through) (our|a) (approved )?vendor"),
    ("chat interview", r"interviews? (will be |are )?(conducted |held )?(via|on|over) (telegram|whatsapp|signal|google hangouts|hangouts|teams chat|text)|"
                       r"(add|contact|message) (us|the (hiring )?manager) on (telegram|whatsapp|signal)"),
    ("odd pay", r"paid (in|with|via) (crypto|bitcoin|usdt|gift ?cards?)|weekly pay via (zelle|cash ?app|venmo)"),
    ("early identity ask", r"(send|provide|submit) (us )?(your )?(ssn|social security( number)?|bank (account|details|information)|routing number|"
                           r"driver'?s licen[cs]e (photo|copy)|passport copy)( (now|immediately|before))?"),
    ("too good", r"no experience (needed|required)[^.]{0,80}\$\s?\d{2,3}\s?(/|per) ?(hour|hr)|earn \$\d{3,}[^.]{0,20}(per|a) day"),
    ("reshipping", r"reship(ping)?|package (forwarding|inspection) (agent|assistant)|receive and (re)?ship packages"),
]
_RED = [(n, re.compile(p, re.I)) for n, p in RED_FLAGS]
APPLY_BY_FREE_MAIL = re.compile(r"(send|email|forward) (your )?(resume|cv|application)[^.]{0,60}@(" + FREE_MAIL + r")\.(com|net|org)\b", re.I)


def host_ok(url):
    """(ok, reason). Known ATS host -> ok; known bad host -> never; anything else -> not auto-filled."""
    host = (urlparse(url or "").hostname or "").lower()
    if not host:
        return False, "no application URL"
    if NEVER_HOSTS.search(host):
        return False, f"untrusted host {host}"
    if ATS_HOSTS.search(host):
        return True, ""
    return False, f"not an ATS host ({host}): open it yourself"


def jd_flags(jd):
    """Red-flag names found in a job description (empty list = none)."""
    low = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(html.unescape(jd or ""))).split())
    out = [n for n, rx in _RED if rx.search(low)]
    if APPLY_BY_FREE_MAIL.search(low):
        out.append("apply via free-mail address")
    return out


def verdict(url, jd="", company=""):
    """(ok, reasons): ok only when the host is trusted and the description has no scam red flags."""
    reasons = []
    ok, why = host_ok(url)
    if not ok:
        reasons.append(why)
    reasons += [f"scam signal: {f}" for f in jd_flags(jd)]
    return not reasons, reasons


def message_flags(sender, subject, body):
    """Scam signals in a recruiting email: free-mail 'recruiter' plus a money / identity / chat-app ask, or a
    look-alike sender name. Used by the inbox loop; never replies to or clicks anything."""
    text = f"{subject} {body}".lower()
    flags = [n for n, rx in _RED if rx.search(text)]
    m = re.search(r"@([a-z0-9.-]+)", (sender or "").lower())
    dom = m.group(1) if m else ""
    if re.fullmatch(r"(" + FREE_MAIL + r")\.(com|net|org|co\.uk)", dom) and re.search(r"offer|interview|position|hiring|recruit", text):
        flags.append("recruiter on a free-mail domain")
    return flags
