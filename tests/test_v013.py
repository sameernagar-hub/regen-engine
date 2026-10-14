"""v0.13 Reach: Workday / iCIMS / SmartRecruiters adapters (offline, faked HTTP), the reach list, the supervisor's
container inventory and saved benchmarks."""
import json, os, time

from engine.discovery import ats as A
from engine.config import WORKSPACE


def test_harvest_reach_boards():
    found = A.harvest_urls([
        "https://acme.wd5.myworkdayjobs.com/en-US/Acme_Careers/job/US-CA-Irvine/Engineer_R123",
        "https://beta.wd1.myworkdayjobs.com/External/job/x_R9",
        "https://jobs.smartrecruiters.com/AcmeCorp/744000155407259",
        "https://careers-acme.icims.com/jobs/7099/engineer/job",
    ])
    assert found["workday"] == {"acme.wd5/Acme_Careers", "beta.wd1/External"}
    assert found["smartrecruiters"] == {"AcmeCorp"}
    assert found["icims"] == {"careers-acme"}


def test_workday_dates_and_locations():
    assert A._wd_days("Posted Today") == 0 and A._wd_days("Posted Yesterday") == 1
    assert A._wd_days("Posted 30+ Days Ago") == 30 and A._wd_days("soon") is None
    j = {"locationsText": "3 Locations", "externalPath": "/job/California---San-Francisco/ML-Engineer_JR1"}
    assert A._wd_where(j) == "California, San Francisco (+3 locations)"
    assert A._icims_where("US-VA-Norfolk") == "Norfolk, VA, US"


def test_workday_stops_at_old_postings(monkeypatch):
    calls = []

    def fake(url, body, timeout=20):
        calls.append(body["offset"])
        fresh = [{"title": f"Software Engineer {i}", "externalPath": f"/job/US-CA-Irvine/SWE_R{body['offset'] + i}",
                  "locationsText": "US-CA-Irvine", "postedOn": "Posted 2 Days Ago"} for i in range(19)]
        return {"jobPostings": fresh + [{"title": "Old", "externalPath": "/job/x/Old_R0", "postedOn": "Posted 30+ Days Ago"}]}
    monkeypatch.setattr(A, "_post", fake)
    out = A.workday("acme.wd5/Acme_Careers")
    assert calls == [0]  # the first page already reached old postings: no second call
    assert len(out) == 19 and out[0]["id"] == "R0_acme" and out[0]["url"].startswith("https://acme.wd5.myworkdayjobs.com/en-US/Acme_Careers/job/")


CARD = ('<li class="iCIMS_JobCardItem"><a href="https://careers-acme.icims.com/jobs/{n}/swe/job?in_iframe=1" class="iCIMS_Anchor" '
        'title="{n} - SWE"><h3 >\nSoftware Engineer {n}</h3></a><dt class="iCIMS_JobHeaderField">'
        '<span class="sr-only field-label">Location : Location</span>\n</dt>\n<dd class="iCIMS_JobHeaderData"><span >\nUS-CA-Irvine</span></dd></li>')


def test_icims_first_seen_dates(monkeypatch):
    pages = {"a": "<ul>" + CARD.format(n=1) + "</ul>"}
    monkeypatch.setattr(A, "_html", lambda url, timeout=20: pages["a"])
    seen = {}
    first = A.icims("careers-acme", _seen=seen)
    assert first[0]["posted"].startswith("2000") and first[0]["location"] == "Irvine, CA, US"  # already open: old, no flood
    pages["a"] = "<ul>" + CARD.format(n=2) + CARD.format(n=1) + "</ul>"
    again = {j["id"]: j for j in A.icims("careers-acme", _seen=seen)}
    assert again["1_careers-acme"]["posted"].startswith("2000")
    assert again["2_careers-acme"]["posted"] > "2026"  # new since the last pass: dated now
    assert again["2_careers-acme"]["title"] == "Software Engineer 2"


def test_smartrecruiters_mapping(monkeypatch):
    monkeypatch.setattr(A, "_get", lambda url, timeout=20, retries=2: {"totalFound": 1, "content": [{
        "id": "744", "name": "Backend Engineer", "releasedDate": "2026-10-13T02:47:40.744Z", "company": {"name": "Acme"},
        "location": {"city": "Austin", "region": "TX", "country": "us", "remote": True, "fullLocation": "Austin, TX, United States"}}]})
    j = A.smartrecruiters("AcmeCorp")[0]
    assert j["company"] == "Acme" and j["location"] == "Austin, TX, United States (Remote)"
    assert j["url"] == "https://jobs.smartrecruiters.com/AcmeCorp/744" and j["posted"] == "2026-10-13T02:47:40+00:00"


def test_reach_pick_only_new_reach_jobs():
    from engine.discovery.reach import pick
    q = [{"ats": "greenhouse", "url": "g", "posted": "2026-10-13"},
         {"ats": "workday", "url": "w1", "posted": "2026-10-12"}, {"ats": "icims", "url": "i1", "posted": "2026-10-13"},
         {"ats": "smartrecruiters", "url": "s1", "posted": "2026-10-11"}]
    got = pick(q, [{"url": "w1"}], 5)
    assert [j["url"] for j in got] == ["i1", "s1"]  # newest first, greenhouse and already-listed left out


def test_reach_write_lists_only_built_rows():
    from engine.discovery import reach as R
    R.write([{"listed": "2026-10-13T10:00:00", "ats": "workday", "company": "Acme", "title": "SWE", "url": "u1",
              "resume": "out/Resume_Acme_R1.pdf", "lane": "backend"},
             {"listed": "2026-10-13T10:00:00", "ats": "icims", "company": "Beta", "title": "QA", "url": "u2", "skipped": True}])
    md = open(os.path.join(WORKSPACE, "reach.md"), encoding="utf-8").read()
    assert "[SWE](u1)" in md and "u2" not in md
    assert len(R.load()) == 2


def test_cpu_mem_from_one_stats_sample():
    from engine.supervisor import _cpu_mem
    st = {"cpu_stats": {"cpu_usage": {"total_usage": 300}, "system_cpu_usage": 2000, "online_cpus": 4},
          "precpu_stats": {"cpu_usage": {"total_usage": 100}, "system_cpu_usage": 1000},
          "memory_stats": {"usage": 300 * 2 ** 20, "limit": 1024 * 2 ** 20, "stats": {"inactive_file": 44 * 2 ** 20}}}
    assert _cpu_mem(st) == (80.0, 256, 1024)
    assert _cpu_mem({}) == (0.0, 0, 0)


def test_containers_snapshot_staleness():
    from engine import supervisor as S
    json.dump({"ts": time.time(), "containers": [], "totals": {}}, open(S.CONTAINERS, "w"))
    assert S.containers()["age"] <= 1 and "stale" not in S.containers()
    json.dump({"ts": time.time() - 900, "containers": [], "totals": {}}, open(S.CONTAINERS, "w"))
    assert S.containers()["stale"] is True


def test_bench_save_and_latest():
    from engine import bench as B
    rec = B.save({"B5_rate": {"best_per_h": 16.3}})
    assert B.latest()["results"] == rec["results"] == {"B5_rate": {"best_per_h": 16.3}}
    r = B.b3_claims(workers=4, batches=40)
    assert r["exactly_once"] is True


def test_api_reach_bench_containers():
    from fastapi.testclient import TestClient
    from apps.api.main import app
    c = TestClient(app)
    assert "results" in c.get("/api/control/bench").json()
    r = c.get("/api/control/reach").json()
    assert set(r) == {"rows", "listed", "gated", "by_ats"}
    assert "containers" in c.get("/api/control/containers").json()


def test_linkedin_alert_cards_from_plain_text():
    from engine.discovery.alerts import linkedin_cards
    text = """Your job alert for Software Engineer in California
Manage your job alerts:  https://www.linkedin.com/comm/jobs/alerts?x=1

Software Engineer, Voice Agents
Initech
Mountain View, CA

2 school alumni
View job: https://www.linkedin.com/comm/jobs/view/1/?a=b

---------------------------------------------------------

Full Stack Engineer
Globex
California, United States
View job: https://www.linkedin.com/comm/jobs/view/2/?a=b

See all jobs: https://www.linkedin.com/comm/jobs/search"""
    rows = linkedin_cards(text, "Tue, 13 Oct 2026")
    assert [(r["title"], r["company"], r["location"]) for r in rows] == [
        ("Software Engineer, Voice Agents", "Initech", "Mountain View, CA"),
        ("Full Stack Engineer", "Globex", "California, United States")]


def test_rejection_wordings_seen_10_13():
    """Real rejection sentences that were stored as confirmations before 10-13 (names replaced), plus two
    confirmations whose conditional "if not selected" wording must stay confirmations."""
    from engine.feedback.inbox import classify
    rej = [("Thank you for applying to Initech", "After careful review, we unfortunately do not have an immediate opening that aligns."),
           ("Important information about your application", "After careful consideration, unfortunately, we won't be proceeding with your application any further."),
           ("Application: Status update", "we have decided to progress with other candidates"),
           ("Update on your application", "unfortunately are going in a direction that better fits our needs at this time."),
           ("[Update] Your Job Application", "We have now filled all of our openings for this role and will not be moving forward"),
           ("Thank you for your application", "The hiring manager has chosen to move forward with another candidate"),
           ("Application Status", "are not an exact match for the requirements of this role. As a result, we will not be moving forward")]
    ok = [("Thank You for Applying at Globex", "we get hundreds of applications and unfortunately we cannot respond individually. If you are not selected, we keep you in mind."),
          ("Thank you for applying", "If you don't get selected to move forward, we hope you consider us."),
          ("Thank you for applying", "If it is not a strong match for this position, we will keep your application on file")]
    assert [classify(s, b) for s, b in rej] == ["rejection"] * len(rej)
    assert [classify(s, b) for s, b in ok] == ["confirmation"] * len(ok)


def test_body_text_decodes_html_parts():
    import email
    from engine.feedback.inbox import body_text
    raw = ("Content-Type: text/html; charset=utf-8\nContent-Transfer-Encoding: base64\n\n"
           + __import__("base64").b64encode(b"<p>Thank you.</p><style>p{}</style><p>Unfortunately, we&#39;ve decided not to move forward.</p>").decode())
    assert body_text(email.message_from_string(raw)) == "Thank you. Unfortunately, we've decided not to move forward."


def test_outcomes_latest_per_message_and_void():
    from engine.feedback import events
    events._cache.update(path=None)
    events.record("outcome", msg_id="<m1>", outcome="confirmation", company="Initech")
    events.record("outcome", msg_id="<m1>", outcome="rejection", company="Initech")   # corrected on a re-read
    events.record("outcome", msg_id="<m2>", outcome="scam", company=None)
    events.record("outcome", msg_id="<m2>", outcome="void", reason="own sent mail")  # retracted
    got = {e["msg_id"]: e["outcome"] for e in events.read("outcome") if e.get("msg_id") in ("<m1>", "<m2>")}
    assert got == {"<m1>": "rejection"}


def test_own_mail_and_newsletters_are_not_outcomes(monkeypatch):
    from engine.feedback import inbox
    monkeypatch.setattr(inbox, "own_addresses", lambda: {"jane.doe@example.com"})
    monkeypatch.setattr(inbox, "applied_companies", lambda: {"Initech": [{"job": "Initech - SWE"}]})
    new = inbox.ingest([
        {"id": "<a>", "from": "Jane <jane.doe@example.com>", "subject": "Re: your hiring post", "snippet": "interview offer position"},
        {"id": "<b>", "from": "news@example.com", "subject": "Top demos #48", "snippet": "web agents and classifiers"},
        {"id": "<c>", "from": "no-reply@example.com", "subject": "Update on your Initech application",
         "snippet": "Unfortunately, we have decided to move forward with other candidates. Globex Box"}])
    assert [(e["outcome"], e["company"]) for e in new] == [("rejection", "Initech")]
