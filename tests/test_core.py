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
    f = harvest_urls(["https://job-boards.greenhouse.io/Stripe/jobs/1", "https://jobs.ashbyhq.com/Clay/abc",
                      "https://jobs.lever.co/palantir/xyz/apply", "https://boards.greenhouse.io/embed/job_app?for=reddit&token=2"])
    assert f["greenhouse"] == {"stripe", "reddit"}
    assert f["ashby"] == {"Clay"}           # Ashby tokens are case-sensitive
    assert f["lever"] == {"palantir"}


def test_slugs():
    s = slugs("The D. E. Shaw Group")
    assert "deshaw" in s
    assert "chime" in slugs("Chime Financial, Inc")


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
    assert answer_for("What is the earliest you would want to start?", {}).startswith("Immediately")


def test_pick_option():
    assert pick_option([("I have read and agree", 1), ("I do not agree", 2)], "__ACK__") == 1
    assert pick_option([("No", 1), ("Yes, I acknowledge", 2)], "__ACK__") == 2
    assert pick_option([("Not now", 1)], "__ACK__") is None
    assert pick_option([("Yes", 1), ("Decline to self-identify", 2)], "__DECLINE__") == 2
    assert pick_option([("San Jose, California, United States", 1), ("San Jose, Costa Rica", 2)], "San Jose") == 1
    assert pick_option([("London", 1), ("San Francisco", 2)], "San Francisco Bay Area") == 2
    assert pick_option([("No", 1), ("Yes", 2)], "Immediately (2 weeks notice)") is None
