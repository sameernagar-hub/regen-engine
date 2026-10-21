"""The real form filler (engine/apply/runner.py) in headless Chromium against local look-alikes of Greenhouse,
Ashby and Lever forms (tests/fixtures/forms). Network requests to the ATS hosts are intercepted and answered with
the fixture page, so the runner's own URL handling, scheduler, airbags, proof screenshots and event log all run
for real, and nothing leaves the machine. Skipped when Playwright's Chromium isn't installed."""
import json, os, re

import pytest

pw_api = pytest.importorskip("playwright.sync_api")

from engine.apply import runner as R
from engine.apply.scheduler import Quantum, RoundRobin, Task
from engine.config import WORKSPACE, in_workspace
from engine.feedback import events

FORMS = os.path.join(os.path.dirname(__file__), "fixtures", "forms")
ATS = re.compile(r"^https://(job-boards\.greenhouse\.io|jobs\.ashbyhq\.com|jobs\.lever\.co|apply\.workable\.com)/")


@pytest.fixture(scope="module")
def browser():
    with pw_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as e:  # browsers not installed (e.g. a minimal CI image)
            pytest.skip(f"chromium not available: {e}")
        yield b
        b.close()


@pytest.fixture(autouse=True)
def workspace():
    os.makedirs(os.path.join(WORKSPACE, "out"), exist_ok=True)
    os.makedirs(os.path.join(WORKSPACE, "specs"), exist_ok=True)
    open(os.path.join(WORKSPACE, "out", "Resume_Initech_1.pdf"), "wb").write(b"%PDF-1.4\n%fixture\n")
    json.dump({"roles": [["acme", ["x_api"]]]}, open(os.path.join(WORKSPACE, "specs", "Initech_1.json"), "w"))
    events._cache.update(path=None)
    yield


def apply_one(browser, fixture, job, dry=False):
    html = open(os.path.join(FORMS, fixture), encoding="utf-8").read()
    page = browser.new_page()
    page.route(ATS, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.set_default_timeout(8000)
    results = []
    with in_workspace():
        rr = RoundRobin(Quantum(), concurrency=1)
        done = rr.run([Task(job["name"], R.ats_key(job["url"]), lambda pg: R.job_task(pg, job, dry, results))], [page])
        state = page.evaluate("() => ({submitted: window.__submitted || null, spons: window.__spons || null, eeo: window.__eeo || null, auth: window.__auth || null, w: window.__w || null})")
    page.close()
    assert not done[0].error, done[0].error
    return done[0].result, results[0], state


def latest(job):
    return [e for e in events.read("application") if e["job"] == job][-1]


def test_greenhouse_end_to_end(browser):
    job = {"name": "Initech - Backend Engineer", "url": "https://job-boards.greenhouse.io/initech/jobs/1",
           "resume": "out/Resume_Initech_1.pdf"}
    status, res, state = apply_one(browser, "greenhouse.html", job)
    assert status == "SUBMITTED", status
    assert state["submitted"]["spons"] == R.P["needs_sponsorship_now_or_future"]       # legal answer from presets
    assert "I built 12 production REST APIs" in state["submitted"]["why"]                # Fact Bank draft, no LLM
    assert state["submitted"]["employment"] == ["Acme Corp", "Software Engineer", "2023", "January", True]  # Fact Bank role
    ev = latest(job["name"])
    assert ev["status"] == "SUBMITTED" and os.path.exists(os.path.join(WORKSPACE, ev["proof"]))   # proof on disk
    assert ev["drafted"][0][2] == ["x_api"]                                                       # draft is traceable
    assert os.path.exists(os.path.join(WORKSPACE, "drafts_review.md"))


def test_greenhouse_dry_run_never_submits(browser):
    job = {"name": "Initech - Backend Engineer (dry)", "url": "https://job-boards.greenhouse.io/initech/jobs/1",
           "resume": "out/Resume_Initech_1.pdf"}
    status, _, state = apply_one(browser, "greenhouse.html", job, dry=True)
    assert status == "filled (dry run)" and state["submitted"] is None


def test_ashby_late_required_question_goes_to_you(browser):
    """The follow-up only appears after the sponsorship answer and its asterisk is CSS-only: it must be seen as
    required and unanswered, so the job is not submitted (a 10-07 failure)."""
    job = {"name": "Globex - AI Engineer", "url": "https://jobs.ashbyhq.com/globex/2", "resume": "out/Resume_Initech_1.pdf"}
    status, _, state = apply_one(browser, "ashby.html", job)
    assert status.startswith("NEEDS YOU") and "obscure mainframe" in status, status
    assert state["spons"] == R.P["needs_sponsorship_now_or_future"]


def test_ashby_submits_when_follow_up_is_answerable(browser):
    job = {"name": "Globex - AI Engineer 2", "url": "https://jobs.ashbyhq.com/globex/3", "resume": "out/Resume_Initech_1.pdf",
           "extra": {"obscure mainframe": "No"}, "note": "A reviewed note for this job."}
    status, _, state = apply_one(browser, "ashby.html", job)
    assert status == "SUBMITTED", status
    # region-only place search: the user's own state ("Springfield, IL" has an abbreviation -> the country), never
    # another city; "How did you hear" outside a field entry -> Other + the careers-page answer in its box
    assert state["w"] == {"loc": "United States", "hear": "Other", "other": "Company careers page"}, state["w"]


def test_ashby_location_that_asks_for_the_country(browser):
    job = {"name": "Globex - Platform Engineer", "url": "https://jobs.ashbyhq.com/globex/4", "resume": "out/Resume_Initech_1.pdf"}
    status, _, state = apply_one(browser, "ashby_country.html", job)
    assert status == "SUBMITTED", status
    assert state["w"] == {"loc": R.P["country"]}, state["w"]


def test_ashby_captcha_goes_to_you_and_starts_the_cooldown(browser):
    job = {"name": "Globex - Data Engineer", "url": "https://jobs.ashbyhq.com/globex/5", "resume": "out/Resume_Initech_1.pdf"}
    cool = os.path.join(WORKSPACE, "ashby_cooldown")
    try:
        status, _, _ = apply_one(browser, "ashby_captcha.html", job)
        assert status.startswith("FAILED: CAPTCHA"), status
        assert os.path.exists(cool)  # Ashby is suspicious: no more Ashby submits until the cooldown ends
    finally:
        if os.path.exists(cool):
            os.remove(cool)


def test_lever_end_to_end_declines_eeo(browser):
    job = {"name": "Umbrella - Software Engineer", "url": "https://jobs.lever.co/umbrella/abc", "resume": "out/Resume_Initech_1.pdf"}
    status, _, state = apply_one(browser, "lever.html", job)
    assert status == "SUBMITTED", status
    assert state["eeo"] == "d" and state["auth"] == "y"


def test_unknown_site_goes_to_you(browser):
    job = {"name": "Hooli - SWE", "url": "https://hooli.wd5.myworkdayjobs.com/x", "resume": "out/Resume_Initech_1.pdf", "ats": "workday"}
    page = browser.new_page()
    results = []
    with in_workspace():
        g = R.job_task(page, job, False, results)
        with pytest.raises(StopIteration) as stop:
            next(g)
    page.close()
    assert stop.value.value.startswith("NEEDS YOU: no adapter for workday")


def test_interleave_spreads_companies():
    jobs = [{"name": f"{c} - r{i}", "url": f"u{c}{i}"} for c, i in [("A", 1), ("A", 2), ("A", 3), ("B", 1), ("C", 1)]]
    assert [j["name"][0] for j in R.interleave(jobs)] == ["A", "B", "C", "A", "A"]


def test_workable_end_to_end(browser):
    job = {"name": "Hooli - Backend Engineer", "url": "https://apply.workable.com/hooli/j/ABC123/", "resume": "out/Resume_Initech_1.pdf"}
    status, _, state = apply_one(browser, "workable.html", job)
    assert status == "SUBMITTED", status
    w = state["w"]
    assert w["first"] == R.P["first_name"] and w["address"].startswith(R.P["city"])
    assert w["spons"] == R.P["needs_sponsorship_now_or_future"]
    assert "I built 12 production REST APIs" in w["why"]


def test_b2_rules_from_presets():
    """B2 (10-11): own-city 'based in', transitioning service member, contractor on behalf of, eligible for employment."""
    city = R.P.get("city")
    if city:
        assert R.answer_for(f"Are you currently based in {city}?", {}) == "Yes"
    assert R.answer_for("Are you a transitioning service member?", {}) == R.P.get("transitioning_service_member", R.P.get("us_military_reserve"))
    assert R.answer_for("Are you legally eligible for employment in the US?", {}) == R.P.get("work_authorized_us")
    assert R.answer_for("Are you currently performing work on behalf of Acme as a contractor?", {}) == R.P.get("former_contractor_of_company")


def _opts(*texts):
    return [(t, i) for i, t in enumerate(texts)]


def test_option_fallback_real_option_lists():
    """10-11: option lists that stopped a whole pass (answers existed, wording differed)."""
    src = _opts("College Career Fair", "Dice", "LinkedIn", "Acme Website", "Referral", "Other")
    assert R.pick_option(src, "Company careers page") == 3
    assert R.pick_option(_opts("Career Fair/Conference", "Acme Career Site", "LinkedIn"), "Company careers page") == 1
    assert R.pick_option(_opts("Careers Website", "LinkedIn", "Other"), "Company website") == 0
    edu = _opts("High School", "Associate's Degree", "Bachelor's Degree", "Masters's Degree", "Other")
    assert R.pick_option(edu, "Master's degree") == 3
    travel = _opts("0%", "1-10%", "11-20%", "21-30%", "75%+")
    assert R.pick_option(travel, "Up to 25%") == 2
    ack = _opts("I understand that this role requires a minimum of 2 days a week in office")
    assert R.pick_option(ack, "Yes") == 0
    elig = _opts("I am eligible to work in the country of my application without sponsorship now or in the future",
                 "I require sponsorship in the country of my application now or in the future")
    need = R.P.get("needs_sponsorship_now_or_future")
    if need in ("Yes", "No"):
        assert R.pick_option(elig, "Student visa") == (1 if need == "Yes" else 0)
    city = R.P.get("city")
    if city:
        loc = _opts("I am located within a commutable distance to Springfield, IL.",
                    "I am not currently located within a commutable distance near either office.")
        assert R.pick_option(loc, f"{city}, California") == 1
    assert R.pick_option(_opts("Yes", "No"), "Up to 25%") is None  # never guesses


def test_completed_bachelors_is_yes_no():
    assert R.answer_for("Have you completed the following level of education: Bachelor's Degree?", {}) == R.P.get("has_degree")


def test_needs_backlog_rules():
    """10-11 /needs backlog: yes/no name check, referral, address phrasings."""
    assert R.answer_for("Have you added your full legal name and surname (including any middle names)?", {}) == "__ACK__"
    assert R.answer_for("Did someone refer you to apply to this role?", {}) == R.P.get("referred", "No")
    if R.P.get("address_line1") and not R.P["address_line1"].startswith("<"):  # profile.example placeholders never fill
        assert R.P["address_line1"] in R.answer_for("What is your current address?", {})
        assert R.P["address_line1"] in R.answer_for("Please provide your current address.", {})


def test_years_question_is_yes_no():
    """10-11: 'Do you have at least two years of ... ?' got the number '3'."""
    y = R.P.get("years_experience")
    if not str(y).isdigit():
        return
    assert R.years_yesno(f"Do you have at least {int(y) + 2} years of experience with Kubernetes?") == "No"
    assert R.years_yesno("Do you have at least two years of professional experience developing backend applications?") in ("Yes", None)
    assert R.years_yesno("What is your name?") is None


def test_current_role_picks_present_then_latest():
    roles = {"a": ["Old Co", "Engineer", "X", "Jan 2020 - Mar 2022"], "b": ["Now Co", "Lead", "Y", "July 2026 - Present"],
             "c": ["Mid Co", "SWE", "Z", "Apr 2022 - Jun 2026"], "bad": ["?", "?"]}
    r = R.current_role({"roles": roles})
    assert r == {"company": "Now Co", "title": "Lead", "start_month": "July", "start_year": "2026", "end_month": None,
                 "end_year": None, "current": True}
    del roles["b"]
    assert R.current_role({"roles": roles})["company"] == "Mid Co"
    assert R.current_role({"roles": {}}) is None


def test_visa_explain_license_and_marketing_optin():
    """10-20 parked questions: visa explanation, securities licenses, marketing opt-in."""
    from engine.apply import runner as R
    q = "If sponsorship is needed, please explain your current visa type and status."
    assert R.answer_for(q, {}) == R.P.get("work_auth_status")
    q = "Do you currently hold or have previously held any securities industry licenses (ie - SEC, FINRA)?"
    assert R.answer_for(q, {}) == R.P.get("securities_license", "No")
    q = "You can choose to receive recruitment marketing communications from us, including updates on new roles."
    assert R.answer_for(q, {}) == "No"
