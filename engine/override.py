"""Human override (user, 2026-10-17): "when I say draft, then draft". One switch the user flips; while it is on, the
engine drafts and submits where it would otherwise park a job for the user.

    python -m engine draft on [note]     the user's standing approval, logged with time and note
    python -m engine draft off
    python -m engine draft status

State lives in profile/override.json (git-ignored, in the bank volume): {"draft": true, "since": iso, "note": ...}.

What the override answers (each answer is recorded on the job as drafted with source "user override"):
  agreements    arbitration, dispute clauses, terms, codes of conduct, certifications -> accepted (the user's consent)
  export        "U.S. person?" / sanctioned-country / "does the deemed export rule affect you?" -> from your citizenship
                and U.S.-person presets, never guessed
  identity      pronouns -> declined; addresses -> your address preset; documentation / verification -> Yes
  open text     anything else non-factual -> a Fact Bank draft (forced), as the drafter does for open questions
What it never does, override or not:
  - answer a FACT about you that is not on file (criminal record, vaccination, a product you have used, a pending
    immigration case, devices you own...): those stay parked and are listed by `engine draft status` so you answer
    each once (it becomes a preset)
  - touch a captcha, a bot check or a "prove you are a person" question
  - answer EEO / demographic questions with anything but a decline
"""
import datetime, json, os, re, sys

from engine.config import PROFILE

PATH = os.path.join(PROFILE, "override.json")

# facts only the user knows: never drafted, never defaulted
FACT_ONLY = re.compile(r"convict|felony|misdemeanor|indict|criminal (record|history)|vaccin|have you used \w+ before|"
                       r"used .{0,30} before\?|which of these devices|devices do you (have|own)|active immigration case|"
                       r"credit report|bankruptcy|foreclosure|transcript|video|which .{0,40}did you attend", re.I)
# a check that a human is filling the form: never automated
HUMAN_CHECK = re.compile(r"completed by a person|carefully read (the )?instructions|select the (first|second|third|last) "
                         r"option|captcha|human check|are you a (robot|human)|access code you received", re.I)
AGREEMENT = re.compile(r"arbitrat|any disputes|agreement to arbitrate|terms (&|and) conditions|code of conduct|"
                       r"confidential information|affirmation|personal information policy|review the linked document|"
                       r"^\W*(i |by )?(certify|agree|acknowledge|understand|attest)|please (review|read) .{0,60}(agreement|policy|document)", re.I)
US_PERSON = re.compile(r"u\.?s\.? person|lawful permanent resident|u\.?s\.? citizen or national|(asylee|refugee)|"
                       r"22 c\.?f\.?r|itar|are you (currently )?a (u\.?s\.?|us) citizen", re.I)
SANCTIONED = re.compile(r"belarus|cuba|iran|north korea|syria|crimea|russia|venezuela", re.I)
DEEMED = re.compile(r"deemed export rule affect|export licens|export control", re.I)
ADDRESS = re.compile(r"(legal|physical|home|current|residential|mailing) address|list your (current |home )?address|^\W*address\W*$", re.I)


def state():
    try:
        return json.load(open(PATH, encoding="utf-8"))
    except (OSError, ValueError):
        return {"draft": False}


def on():
    """True while the user's draft override is on. O(1) file read."""
    return bool(state().get("draft"))


def set_state(draft, note=""):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    s = {"draft": bool(draft), "since": datetime.datetime.now().isoformat(timespec="seconds"), "by": "user", "note": note}
    json.dump(s, open(PATH, "w", encoding="utf-8"), indent=1)
    from engine.feedback.events import record
    record("override", draft=bool(draft), note=note)
    return s


def blocked(label):
    """'fact' / 'human' when even the override must leave this question to the user, else None. A fact the user
    has put in presets (criminal record, vaccination, credit, immigration case: 10-18) is answered, not blocked."""
    if HUMAN_CHECK.search(label or ""):
        return "human"
    if FACT_ONLY.search(label or ""):
        from engine.apply.runner import P  # lazy: runner imports this module
        key = next((k for rx, k in PRESET_FACTS if re.search(rx, label or "", re.I)), None)
        return None if key and P.get(key) not in (None, "") else "fact"
    return None


# the FACT_ONLY questions a preset can settle (the runner's RULES use the same keys)
PRESET_FACTS = [(r"convict|felony|misdemeanor|indict|criminal (record|history)", "criminal_record"),
                (r"active immigration case", "active_immigration_case"), (r"vaccin", "covid_vaccinated"),
                (r"credit report|bankruptcy|foreclosure", "adverse_credit")]


def answer(label, P):
    """The override's answer for a question no rule answered, from presets only; None -> draft it or leave it.
    O(patterns)."""
    l = " ".join((label or "").split())
    if blocked(l):
        return None
    us_person = str(P.get("us_citizen_or_us_person_itar", "")).lower() == "yes"
    citizen = P.get("citizenship_country") or ""
    if re.search(r"pronoun", l, re.I):
        return "__DECLINE__"
    if SANCTIONED.search(l) and re.search(r"citizen|national|resident|residency", l, re.I) and citizen:
        return "Yes" if SANCTIONED.search(citizen) else "No"
    if US_PERSON.search(l) and P.get("us_citizen_or_us_person_itar"):
        return "Yes" if us_person else "No"
    if DEEMED.search(l) and P.get("us_citizen_or_us_person_itar"):
        if re.search(r"\blist\b|which countr|countries of", l, re.I):
            return None  # asks you to name your citizenships (Zoox 10-24 got "Yes" from "licensing requirements")
        if re.search(r"affect|require|need", l, re.I):
            return "No" if us_person else "Yes"  # a non-U.S. person is who the deemed export rule covers
        return None  # a self-certification list (pick your status): the option text is the employer's, left to you
    if AGREEMENT.search(l):
        return "__ACK__"
    if ADDRESS.search(l) and P.get("address_line1"):
        return ", ".join(x for x in (P.get("address_line1"), P.get("city"), P.get("state_abbr"), P.get("zip")) if x)
    if re.search(r"(provide|furnish|submit) .{0,40}(documentation|proof|verification)|verification of .{0,40}(identity|authori)", l, re.I):
        return "Yes"
    if re.search(r"background (check|screen|investigation)|consumer (and/or )?investigative report", l, re.I):
        return P.get("willing_background_check")
    if re.search(r"type of (visa|sponsorship)|which type of visa|^\W*visa\W*$", l, re.I) and P.get("work_auth_status"):
        return f"{P['work_auth_status']}; will need H-1B sponsorship in the future" if str(
            P.get("needs_sponsorship_now_or_future", "")).lower() == "yes" else P["work_auth_status"]
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "status"
    if cmd in ("on", "off"):
        s = set_state(cmd == "on", " ".join(argv[1:]))
        print(f"draft override {'ON' if s['draft'] else 'OFF'} since {s['since']}")
        return
    s = state()
    print(f"draft override {'ON since ' + s.get('since', '?') if s.get('draft') else 'OFF'}")
    from engine.feedback.answers import missing_questions
    from engine.pipeline import latest_status
    from engine.feedback.events import read
    st, seen, left = latest_status(), set(), {}
    for e in read("application"):
        if e.get("url") and st.get(e["url"]) == "NEEDS YOU":
            for q in missing_questions(e.get("detail") or ""):
                why = blocked(q)
                if why and (e["url"], q) not in seen:
                    seen.add((e["url"], q))
                    left.setdefault((why, q[:120]), 0)
                    left[(why, q[:120])] += 1
    for (why, q), n in sorted(left.items(), key=lambda x: -x[1]):
        print(f"  {n:>3}  {'you (a fact on file once)' if why == 'fact' else 'you (human check)'}: {q}")


if __name__ == "__main__":
    main()
