import json

from engine.discovery.filters import load_domain, keep, us_location
from engine.discovery.ats import harvest_urls
from engine.discovery.newgrad import slugs
from engine.tailoring.tailor import fit, tailor
from engine.tailoring import resume
from engine.apply.runner import answer_for, pick_option


# ---- discovery filters ----
def test_us_location():
    assert us_location("San Francisco, CA")
    assert us_location("Remote - US")
    assert us_location("United States - Remote / Toronto, Canada")
    assert us_location("")
    assert us_location("Remote")
    assert not us_location("Portugal - Remote")
    assert not us_location("London, UK")
    assert not us_location("Bengaluru, India")


def test_keep_titles_levels_companies():
    d = load_domain()
    assert keep(d, "Software Engineer", "New York, NY") is None
    assert keep(d, "Senior Software Engineer", "New York, NY") == "level/title excluded"
    assert keep(d, "VP, Product Engineering", "New York City") == "level/title excluded"
    assert keep(d, "Platform Engineer - Polygraph Required", "Chantilly, VA") == "level/title excluded"
    assert keep(d, "Software Engineer", "Hawthorne, CA", "SpaceX") == "company excluded"
    assert keep(d, "Software Engineer", "Lisbon, Portugal") == "non-US"
    assert keep(d, "Account Executive", "NYC") == "title"


def test_harvest_urls():
    f = harvest_urls(["https://job-boards.greenhouse.io/Globex/jobs/1", "https://jobs.ashbyhq.com/Initech/abc",
                      "https://jobs.lever.co/umbrella/xyz/apply", "https://boards.greenhouse.io/embed/job_app?for=hooli&token=2"])
    assert f["greenhouse"] == {"globex", "hooli"}
    assert f["ashby"] == {"Initech"}           # Ashby tokens are case-sensitive
    assert f["lever"] == {"umbrella"}


def test_slugs():
    s = slugs("The D. E. Shaw Group")
    assert "deshaw" in s
    assert "vandelay" in slugs("Vandelay Industries, Inc")


# ---- JD fit checks ----
def test_fit_years():
    assert fit("5 to 15+ years of software engineering experience") == ["5+ yrs"]
    assert fit("4–7 years of experience in technical roles") == []
    assert fit("2+ years of experience with Python") == []
    assert fit("3-5 years of professional experience") == []


def test_fit_legal_blockers():
    assert "citizenship" in fit("Must be a US citizen and able to work on-site.")
    assert "no sponsorship" in fit("We are unable to sponsor visas for this role.")
    assert "no sponsorship" in fit("This role is not eligible for visa sponsorship.")
    assert "clearance" in fit("Candidates must obtain a secret clearance.")
    assert fit("We sponsor visas and welcome international candidates.") == []


def test_fit_grad_window():
    assert "grad window" in fit("Open to candidates graduating in 2027.")
    assert "grad window" in fit("Class of 2027 only.")
    assert fit("Bachelor's degree by May/June 2027 in Computer Science") == []  # already met by a 2026 grad


# ---- truthful tailoring ----
def test_tailor_stays_in_fact_bank():
    lanes = json.load(open("profile.example/lanes.json", encoding="utf-8"))
    spec = lanes["lanes"][lanes["default"]]
    out = tailor(spec, "We use Kafka, Kubernetes, React and PostgreSQL every day.")
    cov = out.pop("_coverage")
    resume.validate(out)  # raises if anything is not in the bank
    assert [r for r, _ in out["roles"]] == [r for r, _ in spec["roles"]]
    assert [len(f) for _, f in out["roles"]] == [len(f) for _, f in spec["roles"]]
    assert set(cov["on_resume"]) <= set(cov["jd_terms_you_have"])


# ---- apply answers ----
def test_eeo_always_declined_before_other_rules():
    long = ("Do you have a disability or chronic condition (physical, visual, auditory, cognitive, mental, emotional, "
            "or other) that substantially limits one or more of your major life activities")
    assert answer_for(long, {}) == "__DECLINE__"
    assert answer_for("Are you a veteran or active member of the United States Armed Forces?", {}) == "__DECLINE__"
    assert answer_for("Race", {}) == "__DECLINE__"
    assert answer_for("Do you have experience with distributed tracing?", {}) is None


def test_arbitration_needs_explicit_approval():
    assert answer_for("Mutual Arbitration Agreement", {}) is None
    assert answer_for("Mutual Arbitration Agreement", {"arbitrat": "__ACK__"}) == "__ACK__"


def test_rules_dont_overmatch():
    assert answer_for("Major", {}) == "Computer Science"
    assert answer_for("Open source community contributions", {}) is None
    assert answer_for("Are you based in the U.S.? We only hire in the U.S.", {}) == "Yes"
    assert answer_for("What is the earliest you would want to start?", {}) == "Two weeks notice"


def test_pick_option():
    assert pick_option([("I have read and agree", 1), ("I do not agree", 2)], "__ACK__") == 1
    assert pick_option([("No", 1), ("Yes, I acknowledge", 2)], "__ACK__") == 2
    assert pick_option([("Not now", 1)], "__ACK__") is None
    assert pick_option([("Yes", 1), ("Decline to self-identify", 2)], "__DECLINE__") == 2
    assert pick_option([("San Jose, California, United States", 1), ("San Jose, Costa Rica", 2)], "San Jose") == 1
    assert pick_option([("London", 1), ("San Francisco", 2)], "San Francisco Bay Area") == 2
    assert pick_option([("No", 1), ("Yes", 2)], "Immediately (2 weeks notice)") is None


def test_text_fields_never_get_bare_yes_no():
    from engine.apply.runner import text_ok
    label = "What is the address from which you plan on working? If you would need to relocate, please share"
    assert answer_for(label, {}) != "Yes"
    assert not text_ok("Where will you work from if you relocate?", "Yes")
    assert text_ok("Are you open to relocation?", "Yes")
    assert text_ok("LinkedIn", "https://linkedin.com/in/x")


def test_without_sponsorship_is_never_guessed():
    from engine.apply.runner import P
    # answered only from the explicit preset, never by the generic "sponsor -> Yes" rule
    assert answer_for("Are you authorized to work lawfully in the US without sponsorship?", {}) == P.get("authorized_without_sponsorship")
    assert answer_for("Will you now or in the future require visa sponsorship?", {}) == "Yes"


def test_pick_option_ignores_curly_quotes():
    opts = [("High School Diploma/GED", 1), ("Bachelor’s", 2), ("Master’s", 3), ("PhD", 4)]
    assert pick_option(opts, "Master's") == 3


def test_fit_word_boundaries():
    assert fit("Benefits for people leaving the military or becoming disabled.") == []
    assert "citizenship" in fit("This role is subject to ITAR and requires a US person.")


def test_airbags():
    from engine import safety
    assert safety.check_labels(["Social Security Number", "First Name"]) == ["form asks for sensitive data: Social Security Number"]
    assert safety.check_labels(["Application fee (card number)"])
    assert safety.check_labels(["LinkedIn", "Are you authorized to work in the US?"]) == []
    assert safety.check_page("We build payment methods for merchants", "https://job-boards.greenhouse.io/x", "https://job-boards.greenhouse.io/x/jobs/1") == []
    assert safety.check_page("", "https://evil.example.com/apply", "https://job-boards.greenhouse.io/x/jobs/1")
    presets = {"authorized_without_sponsorship": "Yes", "needs_sponsorship_now_or_future": "Yes", "work_authorized_us": "Yes"}
    assert safety.check_answers([["Will you require sponsorship?", "Yes"], ["Authorized to work without sponsorship?", "Yes"]], presets) == []
    assert safety.check_answers([["Will you now or in the future require visa sponsorship?", "No"]], presets)


def test_inbox_classify():
    from engine.feedback.inbox import classify
    assert classify("Thank you for applying to Umbrella", "If there is a fit, someone will reach out to schedule an interview.") == "confirmation"
    assert classify("Next steps", "We'd like to invite you to a phone screen. Please share your availability.") == "interview"
    assert classify("Your application", "Unfortunately, we have decided to move forward with other candidates.") == "rejection"
    assert classify("Coding challenge", "Please complete the HackerRank assessment within 7 days.") == "oa"
    assert classify("Job offer", "Please buy equipment with a gift card and we'll reimburse you") == "scam"
    assert classify("Security code for your application to X", "paste this code") == "other"


def test_live_narration_is_plain_and_evidence_based():
    from engine.live.server import narrate
    n = narrate({"kind": "application", "status": "SUBMITTED", "job": "Acme - New Grad SWE", "proof": "proof/missing.png"})
    assert n["tone"] == "win" and "Proof saved" not in n["text"] and n["verified"] is False   # no proof on disk, no claim
    assert narrate({"kind": "application", "status": "SKIPPED", "job": "Globex - FS", "detail": "JD: 5+ yrs"})["text"] == "Let Globex go: 5+ yrs."
    assert narrate({"kind": "resume", "job": "X - Y"})["text"] == "Wrote a resume for X."
    assert narrate({"kind": "application", "status": "filled (dry run)", "job": "X - Y", "dry": True}) is None
    assert "wants to talk" in narrate({"kind": "outcome", "outcome": "interview", "company": "Hooli"})["text"]


def test_no_personal_defaults_in_code():
    """Every status / eligibility answer must come from presets, never be hardcoded in the engine."""
    import re
    import engine.apply.runner as r
    src = open(r.__file__, encoding="utf-8").read()
    assert not re.search(r', "(Yes|No)"\),', src), "hardcoded Yes/No answer in RULES: move it to presets"
    assert answer_for("Will you now or in the future require visa sponsorship?", {}) == r.P["needs_sponsorship_now_or_future"]


def test_placeholders_are_never_answers():
    assert answer_for("Are you a US citizen?", {"us citizen": "<Yes/No>"}) is None


# ---- email job alerts ----
def test_alert_parse_and_leads():
    from engine.discovery.alerts import parse, leads_from
    text = ("REGEN-ALERTS § linkedin ¦ Software Engineer ¦ Globex ¦ San Francisco Bay Area (On-site) ¦ Tue § "
            "linkedin ¦ Manage alerts ¦ Initech ¦ New York, NY ¦ Tue § glassdoor ¦ Software Engineer ¦ You can edit "
            "your job alert here. ¦ Tukwila, WA ¦ Tue § ziprecruiter ¦ Software Engineer ¦ Motion Recruitment ¦ "
            "Sunnyvale, CA ¦ Tue § handshake ¦ Senior Software Engineer ¦ Hooli ¦ Austin, TX ¦ Tue § END-ALERTS")
    rows = parse(text)
    assert [r["company"] for r in rows] == ["Globex", "Motion Recruitment", "Hooli"]   # badge/header rows dropped
    assert rows[0]["location"] == "San Francisco, CA"
    assert parse("indeed\tSoftware Engineer\tUmbrella\tHayward, CA 94545")[0]["company"] == "Umbrella"
    leads, dropped = leads_from(rows)
    assert [l["company"] for l in leads] == ["Globex"]
    assert dropped == {"staffing/aggregator": 1, "level/title excluded": 1}


def test_education_dates_not_availability(tmp_path):
    from engine.apply import runner
    fb = tmp_path / "fb.json"
    fb.write_text(json.dumps({"education": [["M.S. -- Initech University", "Aug 2024 - May 2026"]]}))
    assert runner.edu_dates(str(fb)) == {"start_month": "August", "start_year": "2024", "end_month": "May", "end_year": "2026"}
    assert runner.edu_dates(str(tmp_path / "missing.json")) == {}
    # education month/year fields never receive the availability answer
    for label in ("Start date month", "Start date year *", "End date year"):
        assert answer_for(label, {}) != runner.P.get("start_date")
    assert answer_for("When can you start?", {}) == runner.P.get("start_date")
