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
ATS = re.compile(r"^https://(job-boards\.greenhouse\.io|jobs\.ashbyhq\.com|jobs\.lever\.co)/")


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
        state = page.evaluate("() => ({submitted: window.__submitted || null, spons: window.__spons || null, eeo: window.__eeo || null, auth: window.__auth || null})")
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
    status, _, _ = apply_one(browser, "ashby.html", job)
    assert status == "SUBMITTED", status


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
