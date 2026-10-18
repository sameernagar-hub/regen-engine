"""v1 release review: answers that went wrong on real forms on 10-17 (parked, not submitted), now pinned."""
from engine.apply.runner import P, answer_for


def test_country_to_work_in_is_a_country():
    q = "Please enter the country you are legally registered to work in."
    assert answer_for(q, {}) == P["country"]
    assert answer_for("Which country are you authorized to work in?", {}) == P["country"]


def test_describe_years_is_not_a_bare_number():
    q = "Describe your experience with Amazon EC2 and Debian Linux. Include key responsibilities and years of experience."
    assert answer_for(q, {}) != P["years_experience"]
    assert answer_for("How many years of professional experience do you have?", {}) == P["years_experience"]


def test_product_names_are_not_link_boxes():
    q = ("Which best describes your experience using AI coding agents (such as Cursor, Claude Code, or GitHub Copilot) "
         "in your software development workflow?")
    assert answer_for(q, {}) != P["github"]
    assert answer_for("GitHub URL", {}) == P["github"]
    assert answer_for("Website", {}) == P["github"]
    assert answer_for("LinkedIn Profile", {}) == P["linkedin"]


def test_in_person_without_hyphen():
    assert answer_for("Are you wanting to work in person?", {}) == P.get("open_to_onsite_or_relocation")


def test_please_do_not_use_ai_goes_to_you():
    from engine.apply.runner import answer
    job = {"name": "Globex - ML Engineer", "url": "https://jobs.ashbyhq.com/globex/9", "note": "A note."}
    assert answer("Why Globex? Please do not use AI.", job) is None
    assert answer("Tell us about a project (without using ChatGPT or other AI tools)", job) is None


def test_challenge_selector_and_no_blind_ashby_retry(tmp_path, monkeypatch):
    from engine import pipeline
    from engine.apply import runner
    assert "recaptcha/api2/bframe" in runner.CHALLENGE
    rows = [{"kind": "application", "url": u, "status": "FAILED", "detail": "FAILED: no confirmation seen (captcha?)"}
            for u in ("https://jobs.ashbyhq.com/globex/1", "https://job-boards.greenhouse.io/initech/jobs/1")]
    monkeypatch.setattr(pipeline, "read", lambda kind=None: rows)
    st = pipeline.latest_status()
    assert st["https://jobs.ashbyhq.com/globex/1"] == "FAILED"            # Ashby: a resubmit reads as spam
    assert st["https://job-boards.greenhouse.io/initech/jobs/1"] == "RETRY"


def test_gone_posting_leaves_the_queue_but_a_fetch_error_stays(tmp_path, monkeypatch):
    import json
    from engine.tailoring import batch as B
    q = [{"id": "1", "company": "Globex", "title": "SWE", "url": "https://x/1", "ats": "greenhouse", "token": "g"},
         {"id": "2", "company": "Initech", "title": "SWE", "url": "https://x/2", "ats": "greenhouse", "token": "i"}]
    monkeypatch.setattr(B, "load_queue", lambda: {j["id"]: j for j in q})
    monkeypatch.setattr(B, "load_lanes", lambda: {"lanes": {}})
    monkeypatch.setattr(B, "in_workspace", __import__("contextlib").nullcontext)
    monkeypatch.chdir(tmp_path)

    def fetch(j):
        if j["id"] == "2":
            raise OSError("timed out")
        return None, "", []  # 404
    monkeypatch.setattr(B, "job_description", fetch)
    seen = []
    monkeypatch.setattr(B, "record", lambda kind, **kw: seen.append(kw))
    B.build("t", ["1", "2"])
    assert [(r["url"], r["status"], r["detail"]) for r in seen] == [("https://x/1", "SKIPPED", "JD: posting is gone")]
