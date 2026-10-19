"""The control room shows the pipeline container's loop as live (it was always 'idle' unless a UI run was started)."""
import json, os, time

from apps.api import control
from engine import supervisor


def _beat(d, state, ts, role="pipeline", **kw):
    json.dump(dict({"role": role, "state": state, "ts": ts}, **kw), open(os.path.join(d, f"{role}_x.json"), "w"))


def test_loop_stages_follow_the_pipeline_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setattr(supervisor, "FLEET", str(tmp_path))
    now = time.time()
    st = lambda: {x["name"]: x["status"] for x in control._loop_steps(now)}
    assert control._loop_steps(now) == []  # no heartbeat: nothing to show
    _beat(tmp_path, "scanning boards", now, stage="discover")
    assert st() == {"discover": "running", "newgrad": "waiting", "feed": "waiting", "apply": "waiting"}
    _beat(tmp_path, "scanning feed", now, stage="feed")
    assert st() == {"discover": "done", "newgrad": "done", "feed": "running", "apply": "waiting"}
    _beat(tmp_path, "waiting for appliers", now)
    assert st() == {"discover": "done", "newgrad": "done", "feed": "done", "apply": "running"}
    _beat(tmp_path, "sleeping until next scan", now)
    assert st()["apply"] == "done"
    _beat(tmp_path, "applying", now, role="applier")  # between passes an applier still works: apply stays live
    assert st()["apply"] == "running" and st()["discover"] == "done"
    _beat(tmp_path, "waiting for appliers", now - 2 * supervisor.STALE["pipeline"])
    assert control._loop_steps(now) == []  # stale heartbeat (container down) is not shown as live


def test_options_from_a_lever_form(monkeypatch):
    """10-18: right answers, wrong option wording -> 'masters' / 140000 / relocation 'yes' were left blank."""
    from engine.apply import runner as R
    monkeypatch.setitem(R.P, "open_to_onsite_or_relocation", "Yes")
    o = lambda *ts: [(t, i) for i, t in enumerate(ts)]
    edu = o("High School", "Some College", "Associate's Degree", "Undergraduate Degree", "Graduate Degree")
    assert R.pick_option(edu, "masters") == 4
    pay = o("Under $65,000", "$65,000 - $70,000", "$70,000 - $75,000", "Over $75,000")
    assert R.pick_option(pay, "140000") == 3 and R.pick_option(pay, "60000") == 0 and R.pick_option(pay, "67000") == 1
    loc = o("I currently live in or near Charlotte, NC and am willing to commute to the office 5 days a week.",
            "I am willing to relocate to Charlotte, NC.", "I do not live in or near Charlotte, NC and am not willing to relocate.")
    assert R.pick_option(loc, "yes") == 1


def test_if_yes_follow_up_stays_blank():
    from engine.apply import runner as R
    assert R.answer("If yes, please provide your LDAP.", {"title": "SWE", "company": "x"}) is None
    assert R.answer("If so, please provide their name and team.", {"title": "SWE", "company": "x"}) is None


def test_scan_merge_records_discovered_once(tmp_path):
    """10-18: the loop's scans queued jobs without a `discovered` event, so Discover read 0 today."""
    from engine.discovery.scan import merge_queue
    from engine.feedback.events import read
    q = str(tmp_path / "queue.json")
    job = {"id": "x1", "ats": "greenhouse", "company": "Acme", "title": "SWE", "url": "https://x/1",
           "posted": "2099-01-01T00:00:00+00:00"}
    before = len([e for e in read("discovered") if e.get("url") == "https://x/1"])
    merge_queue([job], path=q)
    merge_queue([job], path=q)  # already queued: not discovered again
    merge_queue([dict(job, id="x2", url="https://x/2")], path=q, log=False)
    got = [e for e in read("discovered") if e.get("url") in ("https://x/1", "https://x/2")]
    assert len(got) - before == 1 and got[-1]["url"] == "https://x/1"


def test_watchdog_restarts_only_silent_running_containers(tmp_path, monkeypatch):
    monkeypatch.setattr(supervisor, "FLEET", str(tmp_path))
    now = time.time()
    calls = []
    rows = {"pipeline": [{"Id": "p1", "State": "running"}], "relay": [{"Id": "r1", "State": "running"}]}
    def fake(method, path, body=None):
        calls.append((method, path))
        if method == "GET":
            return next((v for k, v in rows.items() if f"service%3D{k}" in path or f"service={k}" in path), [])
    monkeypatch.setattr(supervisor, "_docker", fake)
    monkeypatch.setattr(supervisor, "audit", lambda *a, **k: None)
    _beat(tmp_path, "sleeping until next scan", now - 60)                       # fresh: left alone
    _beat(tmp_path, "listening", now - 3600, role="relay")                      # silent an hour: restarted
    out = supervisor.liveness(now, _restarted={})
    assert out["pipeline"] == "ok" and out["relay"].startswith("restarted")
    assert ("POST", "/containers/r1/restart?t=10") in calls and not any("p1/restart" in c[1] for c in calls)


def test_board_page_title_is_the_same_company():
    """10-18: 'ZETA Careers page' and 'Zeta' listed the same roles; each was submitted twice."""
    from engine.names import company_slug, role_key
    assert role_key("ZETA Careers page - Back-End Engineer") == role_key("Zeta - Back-End Engineer")
    assert company_slug("Acme Jobs") == company_slug("Acme, Inc.") == "acme"
    assert company_slug("Jobs") == "jobs"  # a name that is only the word stays
