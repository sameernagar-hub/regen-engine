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


def test_state_list_degree_years_and_understanding():
    from engine.apply.runner import experience_answer
    assert answer_for(f"Do you live in one of the following states? Arizona, {P['state']}, Colorado, Florida?", {}) == "Yes"
    assert answer_for("Do you live in DC, Delaware, Hawaii, Iowa, Maine?", {}) == ("No" if P["state"] not in "DC Delaware Hawaii Iowa Maine" else "Yes")
    q = "Do you hold a Bachelor's Degree in Computer Science, plus 40 years of professional experience?"
    assert answer_for(q, {}) == "No"
    assert experience_answer("Do you have an understanding of REST APIs?") in ("Yes", None)


def test_legal_right_and_employed_full_time_at():
    assert answer_for("Do you have the legal right to work in the country where you are applying to work?", {}) == P["work_authorized_us"]
    assert answer_for("Have you ever been employed full-time at Globex or its subsidiaries?", {}) == P.get("previous_employer_of_company", "No")


def test_mechanical_product_engineer_is_blocked():
    from engine.tailoring.tailor import fit
    mech = "New Product Engineer. Use 3D CAD (SolidWorks) to design mechanical components, run DFM and tolerance stacks."
    assert "mechanical / manufacturing role" in fit(mech, max_years=99)
    sw = "Product Engineer: build React and Python features; some prototype work with SolidWorks files for 3D CAD exports."
    assert "mechanical / manufacturing role" not in fit(sw, max_years=99)


def test_background_facts_come_from_presets():
    for q, key in (("Have you ever been convicted of a misdemeanor or felony?", "criminal_record"),
                   ("Do you currently have an active immigration case (ex H-1B extension, green card)?", "active_immigration_case"),
                   ("We require all US-based employees to be fully vaccinated against COVID-19", "covid_vaccinated"),
                   ("Have you had any adverse credit reports in the past 10 years (bankruptcy, foreclosure, etc.)?", "adverse_credit")):
        assert answer_for(q, {}) == P.get(key), q  # unset in the fictional fixture -> None -> still asks
    assert answer_for("we ask all candidates to undergo a criminal background check. Are you willing to consent to a background check?", {}) \
        == P.get("willing_background_check")


def test_typed_attestation_is_signed_with_legal_name():
    from engine.apply.runner import attest_text
    q = ("I certify that the facts set forth in this Application for Employment are true and complete to the best of "
         "my knowledge.")
    assert attest_text(q, "__ACK__") == f"{P['first_name']} {P['last_name']}"
    assert attest_text(q, "Yes") == f"{P['first_name']} {P['last_name']}"
    assert attest_text("Please review the linked document:", "__ACK__") is None  # an ack box, not a signature
    assert attest_text(q, "No") is None


def test_office_list_picks_the_posting_city():
    from engine.apply.runner import office_option
    opts = [(c, c) for c in ("Boca Raton, FL", "Boston, MA", "Des Moines, IA", "New York, NY")]
    q = ("Globex is an office-first culture, as such all employees are required to work in the office "
         "Monday-Thursday. Please review the job description to identify the specified location/s for the role.")
    assert office_option(opts, q, "Des Moines, Iowa, United States") == "Des Moines, IA"
    assert office_option(opts, q, "Remote") is None  # no office named -> still asks
    assert office_option(opts, "How did you hear about us?", "Boston, Massachusetts") is None  # not an office question
    assert office_option([("Newark, NJ", 1)], q, "New York, NY") is None  # whole-word city only
