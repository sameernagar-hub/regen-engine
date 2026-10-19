"""The control room shows the pipeline container's loop as live (it was always 'idle' unless a UI run was started)."""
import json, os, time

from apps.api import control
from engine import supervisor


def _beat(d, state, ts):
    json.dump({"role": "pipeline", "state": state, "ts": ts}, open(os.path.join(d, "pipeline_x.json"), "w"))


def test_loop_stages_follow_the_pipeline_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setattr(supervisor, "FLEET", str(tmp_path))
    now = time.time()
    assert control._loop_steps(now) == []  # no heartbeat: nothing to show
    _beat(tmp_path, "scanning and tailoring", now)
    s = {x["name"]: x["status"] for x in control._loop_steps(now)}
    assert s == {"discover": "running", "newgrad": "running", "feed": "running", "apply": "waiting"}
    _beat(tmp_path, "waiting for appliers", now)
    s = {x["name"]: x["status"] for x in control._loop_steps(now)}
    assert s["apply"] == "running" and s["discover"] == "done"
    _beat(tmp_path, "sleeping until next scan", now)
    assert {x["name"]: x["status"] for x in control._loop_steps(now)}["apply"] == "done"
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
