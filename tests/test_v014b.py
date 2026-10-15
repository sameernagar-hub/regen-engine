"""v0.14: eval containers (B8-B10, triggers, reaping) and the Workday filler (engine/apply/workday.py) against a
local Workday look-alike (tests/fixtures/forms/workday.html). Offline: Docker is faked, the posting is a file."""
import json, os, re, time

import pytest

from engine import bench, supervisor as S
from engine.config import WORKSPACE
from engine.feedback import events

FORMS = os.path.join(os.path.dirname(__file__), "fixtures", "forms")


def test_b8_supervisor_scenarios_all_pass():
    r = bench.b8_supervisor()
    assert r["failed"] == [] and r["passed"] == r["total"] >= 7


def test_b9_api_skips_when_unreachable():
    assert "skipped" in bench.b9_api(n=1, base="http://127.0.0.1:9")


def test_save_summary_and_history(tmp_path, monkeypatch):
    import engine.config as C
    monkeypatch.setattr(C, "WORKSPACE", str(tmp_path))
    out = {"B2_answers": {"answerable_pct": 91.0}, "B8_supervisor": {"passed": 7, "total": 7}, "B9_api": {"p95_ms": 12.5},
           "B6_codes": {"error": "x"}}
    rec = bench.save(out, reason="commit", sha="abc1234")
    assert rec["summary"]["supervisor"] == "7/7" and rec["summary"]["errors"] == ["B6_codes"]
    h = bench.history()
    assert len(h) == 1 and h[0]["reason"] == "commit" and h[0]["summary"]["api_p95_ms"] == 12.5


class FakeDocker:
    """Enough of the Docker API for evals(): one running api container (the template) plus eval containers."""
    def __init__(self, evals=()):
        self.evals, self.calls, self.created = list(evals), [], []

    def __call__(self, m, path, body=None):
        self.calls.append((m, path))
        if path.startswith("/containers/json"):
            if "service%3Dapi" in path or "service=api" in path:
                return [{"Id": "api" * 21 + "x", "State": "running", "Labels": {}}]
            return self.evals
        if path.startswith("/containers/api"):
            return {"Config": {"Image": "regen-applier:local", "Env": ["A=1", "REGEN_API_REACH=1"], "User": "regen"},
                    "HostConfig": {"Binds": ["regen-workspace:/data/workspace:rw"], "PortBindings": {"8787/tcp": []},
                                   "Mounts": [{"Source": "/x/.pg_password", "Target": "/run/secrets/pg_password"}]},
                    "NetworkSettings": {"Networks": {"deploy_default": {}}}}
        if path.startswith("/containers/create"):
            self.created.append((path, body))
            return {"Id": "new" * 21 + "x"}
        if path.endswith("/json"):
            return {"State": {"ExitCode": 0}}
        return None


@pytest.fixture
def evalspace(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "WORKSPACE", str(tmp_path))
    acts = []
    monkeypatch.setattr(S, "audit", lambda a, t, **k: acts.append((a, t, k)))
    monkeypatch.setattr(events, "read", lambda kind=None: [])
    os.makedirs(tmp_path / "bench")
    json.dump({"ts": time.time()}, open(tmp_path / "bench" / "latest.json", "w"))  # schedule not due
    return tmp_path, acts


def test_eval_manual_request_launches_one_bounded_container(evalspace, monkeypatch):
    tmp, acts = evalspace
    (tmp / "bench" / "REQUEST").write_text("1")
    d = FakeDocker()
    monkeypatch.setattr(S, "_docker", d)
    launched, running = S.evals(now=time.time(), _last={})
    assert len(launched) == 1 and running == 1 and not (tmp / "bench" / "REQUEST").exists()
    path, body = d.created[0]
    assert body["Labels"]["com.docker.compose.service"] == "eval" and body["Labels"][S.MANAGED] == "supervisor"
    assert body["Cmd"][:4] == ["bench", "--save", "--reason", "manual"] and body["Entrypoint"] == ["python", "-m", "engine"]
    hc = body["HostConfig"]
    assert hc["Memory"] == S.CAPS["eval"]["Memory"] and "PortBindings" not in hc and hc["Mounts"]  # secret kept, no ports
    assert "REGEN_API_REACH=1" not in body["Env"]  # no write switches in an eval
    assert acts[-1][0] == "eval"


def test_eval_commit_trigger_reaps_and_respects_gap(evalspace, monkeypatch):
    tmp, acts = evalspace
    monkeypatch.setattr(events, "read", lambda kind=None: [{"action": "code_pushed", "sha": "abc1234"}])
    assert S.eval_triggers() == [("commit", "abc1234")]
    d = FakeDocker(evals=[{"Id": "e" * 64, "Names": ["/deploy-eval-1"], "State": "exited",
                           "Labels": {"regen.eval-reason": "schedule"}}])
    monkeypatch.setattr(S, "_docker", d)
    last = {}
    launched, _ = S.evals(now=1000.0, _last=last)
    assert acts[0][0] == "eval_done" and ("DELETE", "/containers/" + "e" * 64) in d.calls
    assert launched and (tmp / "bench" / "last_sha").read_text() == "abc1234" and d.created[0][1]["Cmd"][-2:] == ["--sha", "abc1234"]
    assert S.eval_triggers() == []  # evaluated
    (tmp / "bench" / "REQUEST").write_text("1")
    d2 = FakeDocker(evals=[{"Id": "r" * 64, "Names": ["/deploy-eval-2"], "State": "running", "Labels": {"regen.eval-reason": "manual"}}])
    monkeypatch.setattr(S, "_docker", d2)
    assert S.evals(now=1001.0, _last=last)[0] == []  # a manual eval is already running


def test_eval_max_concurrency(evalspace, monkeypatch):
    tmp, _ = evalspace
    (tmp / "bench" / "REQUEST").write_text("1")
    rows = [{"Id": c * 64, "Names": [f"/e{c}"], "State": "running", "Labels": {"regen.eval-reason": "commit"}} for c in "ab"]
    monkeypatch.setattr(S, "_docker", FakeDocker(evals=rows))
    assert S.evals(now=time.time(), _last={}) == ([], 2)


# ---------------- Workday filler ----------------
pw_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with pw_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        yield b
        b.close()


def _job(tmp_path, query=""):
    pdf = tmp_path / "Resume.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%fixture\n")
    return {"name": "Initech - Software Engineer", "extra": {}, "resume": str(pdf),
            "url": "file:///" + os.path.join(FORMS, "workday.html").replace("\\", "/").lstrip("/") + query}


def test_workday_walk_fills_every_step_and_stops_at_review(browser, tmp_path):
    from engine.apply import workday as W
    from engine.apply.runner import P
    page = browser.new_page(); page.set_default_timeout(5000)
    job = _job(tmp_path)
    status = W.walk(page, job, lambda s: None, submit=False)
    assert status.startswith("FILLED"), status
    w = page.evaluate("() => window.__w")
    assert w["legalNameSection_firstName"] == P["first_name"] and w["addressSection_city"] == P["city"] and w["file"] == 1
    assert w["spons"] in ("Yes", "No") and w["age"] == "Yes"
    assert page.evaluate("() => window.__submitted || null") is None  # never submitted without REGEN_WORKDAY_SUBMIT
    page.close()


def test_workday_submit_when_allowed(browser, tmp_path):
    from engine.apply import workday as W
    page = browser.new_page(); page.set_default_timeout(5000)
    assert W.walk(page, _job(tmp_path), lambda s: None, submit=True) == "SUBMITTED"
    page.close()


def test_workday_sign_in_wall_goes_to_the_user(browser, tmp_path):
    from engine.apply import workday as W
    page = browser.new_page(); page.set_default_timeout(5000)
    status = W.walk(page, _job(tmp_path, "?signin=1"), lambda s: None)
    assert status.startswith("NEEDS YOU: sign in") and "6080" in status
    assert page.query_selector("[data-automation-id=password]").input_value() == ""  # never types a password
    page.close()


def test_desk_request_is_atomic_json():
    from engine.apply import workday as W
    p = W.request("https://x.wd5.myworkdayjobs.com/ext/job/1", "Initech - SWE", "out/r.pdf")
    assert json.load(open(p))["resume"] == "out/r.pdf" and not os.path.basename(p).startswith(".")


@pytest.mark.parametrize("q", ["Are you at least 18 years of age?", "Are you at least 18 years old?",
                               "At the time of application, are you 18+ years of age?", "Are you 18 years of age or older?"])
def test_age_question_is_not_years_of_experience(q):
    """10-14: 'at least 18 years of age' went through the years-of-experience rule (18 > 3 -> No) on 3 submissions."""
    from engine.apply.runner import answer_for, P
    assert answer_for(q, {}) == P["over_18"] == "Yes"
    assert answer_for("Do you have at least 5 years of experience with Go?", {}) == "No"


def test_resume_in_blocks_a_form_without_the_file(browser, tmp_path):
    from engine.apply.runner import resume_in
    page = browser.new_page()
    page.set_content("<form><input type=file id=r><p>Upload your resume</p></form>")
    job = {"resume": str(tmp_path / "Resume_X.pdf")}
    assert not resume_in(page, job)
    (tmp_path / "Resume_X.pdf").write_bytes(b"%PDF-1.4\n")
    page.set_input_files("#r", job["resume"])
    assert resume_in(page, job) and resume_in(page, {})
    page.close()


def test_smartrecruiters_desk_fill_stops_before_submit(browser, tmp_path):
    from engine.apply import workday as W
    from engine.apply.runner import P
    page = browser.new_page(); page.set_default_timeout(5000)
    job = _job(tmp_path)
    job["url"] = job["url"].replace("workday.html", "smartrecruiters.html")
    status = W.walk_sr(page, job, lambda s: None)
    assert status.startswith("FILLED"), status
    assert page.input_value("#fn") == P["first_name"] and page.input_value("#em") == P["email"]
    assert page.evaluate("() => document.getElementById('cv').files.length") == 1
    assert page.evaluate("() => window.__submitted || null") is None  # the user clicks Submit
    page.close()


def test_smartrecruiters_bot_check_goes_to_the_user(browser, tmp_path):
    from engine.apply import workday as W
    page = browser.new_page(); page.set_default_timeout(5000)
    job = _job(tmp_path, "?bot=1")
    job["url"] = job["url"].replace("workday.html", "smartrecruiters.html")
    assert W.walk_sr(page, job, lambda s: None).startswith("NEEDS YOU: SmartRecruiters shows a human check")
    page.close()


def test_workday_signin_list_and_internal_sites():
    from engine.discovery.reach import signins, internal, tenant
    row = lambda url: {"ats": "workday", "company": "initech", "url": url, "resume": "out/r.pdf"}
    rows = [row("https://initech.wd5.myworkdayjobs.com/en-US/External/job/A_1"),
            row("https://initech.wd5.myworkdayjobs.com/External/job/B_2"),
            row("https://initech.wd5.myworkdayjobs.com/Contractor_Conversion/job/C_3"),
            row("https://globex.wd1.myworkdayjobs.com/careers/job/D_4"),
            dict(row("https://globex.wd1.myworkdayjobs.com/careers/job/E_5"), resume=None)]
    assert internal(rows[2]["url"]) and not internal(rows[0]["url"])
    assert tenant(rows[0]["url"]) == ("initech.wd5.myworkdayjobs.com", "External")
    s = signins(rows, done={"https://globex.wd1.myworkdayjobs.com/careers/job/D_4"})
    assert s == [{"host": "initech.wd5.myworkdayjobs.com", "company": "initech", "jobs": 2,
                  "url": "https://initech.wd5.myworkdayjobs.com/External"}]


def test_public_feed_masks_names_in_titles_and_ignores_json_keys(tmp_path, monkeypatch):
    """10-14: the feed was blocked by an edge key ("target") and a role title naming a product that is also an
    employer. Keys are schema, not data; a name inside a public title is masked; a real leak still blocks."""
    import engine.live.export as X
    ev = tmp_path / "events.jsonl"
    ev.write_text("\n".join(json.dumps(e) for e in [
        {"kind": "application", "job": "Initech - Platform Engineer", "status": "SUBMITTED", "ts": "2026-10-14T10:00:00"},
        {"kind": "discovered", "company": "target", "ts": "2026-10-14T10:00:00"}]) + "\n")
    monkeypatch.setattr(X, "WORKSPACE", str(tmp_path)); monkeypatch.setattr(X, "SITE", str(tmp_path / "site"))
    monkeypatch.setattr(X, "narrate", lambda e: None)
    monkeypatch.setattr(X, "snapshot", lambda: {"verified": 1, "boards": 1, "verified_jobs": [["Globex", "Initech Administrator", "crm"]]})
    graph = {"nodes": [{"id": "n1", "label": "Initech Administrator"}], "edges": [{"source": "n0", "target": "n1"}]}
    monkeypatch.setattr(X, "public_graph", lambda: graph)
    d = X.build(7)
    assert d["graph"]["nodes"][0]["label"] == "[name] Administrator" and d["verified_roles"][0][0] == "[name] Administrator"
    monkeypatch.setattr(X, "snapshot", lambda: {"verified": 1, "boards": 1, "verified_jobs": [], "last_poll": "target"})
    with pytest.raises(SystemExit, match="target"):
        X.build(7)


@pytest.mark.parametrize("q,want", [
    ("Do you currently reside in the Pacific or Mountain Time Zone?", "tz"),
    ("Do you hold U.S. and/or Canadian citizenship?", "No"),
    ("Please identify your sex.", "__DECLINE__"),
])
def test_rule_gaps_seen_10_14(q, want, monkeypatch):
    """Stops on 10-14 queue jobs: residence time zone (not only 'based in'), held citizenship from the preset,
    sex as an EEO question (decline, user policy)."""
    from engine.apply.runner import answer, P
    monkeypatch.setitem(P, "timezone", "Mountain Time (MT)")
    monkeypatch.setitem(P, "citizenship_country", "India")
    got = answer(q, {"extra": {}})
    if want == "tz":
        assert got == ("Yes" if re.search(r"pacific|mountain", P.get("timezone", ""), re.I) else "No")
    elif want == "No":
        assert got == ("Yes" if P.get("citizenship_country", "").lower() in ("united states", "canada") else "No")
    else:
        assert got == want
