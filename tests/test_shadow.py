"""Shadow (11-06): the user's AI delegate. The gate treats Shadow as the user; Shadow stays truthful; and the four
questions that parked jobs on 11-06 (salary band, how-heard list, start quarter/year, "I hereby certify", permanent
address) are now answered."""
import datetime, json

import pytest

from engine import override as O
from engine.apply.runner import pick_option
from engine.feedback import answers as A
from engine.tailoring.salary import parse_range

P = {"address_line1": "1 Example St", "city": "Springfield", "state_abbr": "IL", "zip": "00000",
     "start_date": "Immediately (2 weeks notice)"}


def test_salary_lands_in_inclusive_band():
    opts = [("$121,000-$140,000", "a"), ("$141,000-$160,000", "b")]
    assert pick_option(opts, "140000") == "a"
    assert pick_option(opts, "143000") == "b"


def test_escaped_greenhouse_pay_range_is_read():
    jd = ("&lt;div class=&quot;pay-range&quot;&gt;&lt;span&gt;$114,983&lt;/span&gt;&lt;span class=&quot;divider&quot;"
          "&gt;&amp;mdash;&lt;/span&gt;&lt;span&gt;$171,890 USD&lt;/span&gt;&lt;/div&gt;")
    assert parse_range(jd) == (114983, 171890)


def test_how_heard_picks_nearest_true_source():
    assert pick_option([("LinkedIn", 1), ("Company Website", 2), ("Referral", 3)], "Company careers page") == 2
    assert pick_option([("Referral", 1), ("Other", 2)], "Company careers page") == 2


def test_certify_address_and_start_quarter():
    assert O.answer("I hereby certify that all information in my application is true and complete", P) == "__ACK__"
    assert O.answer("What is your current permanent address?", P).startswith("1 Example St")
    d = datetime.date.today() + datetime.timedelta(weeks=2)
    assert O.answer("In which quarter would you be available to begin?", P) == f"Q{(d.month - 1) // 3 + 1}"
    assert O.answer("In which year would you be available to begin at Acme?", P) == str(d.year)


def test_shadow_still_never_touches_human_checks_or_unknown_facts():
    assert O.answer("Please complete the captcha", P) is None
    assert O.blocked("Are you a robot?") == "human"


@pytest.fixture
def bank(tmp_path, monkeypatch):
    monkeypatch.setattr("engine.feedback.answers.record", lambda *a, **k: None)
    monkeypatch.setattr("engine.feedback.answer_queue.QDIR", str(tmp_path / "q"))
    (tmp_path / "q").mkdir()
    return tmp_path


def test_gate_treats_shadow_as_the_user(bank):
    q = "Will you now or in the future require visa sponsorship?"
    with pytest.raises(ValueError):
        A.save("Acme - SWE", q, "Yes", profile=str(bank), workspace=str(bank), requeue_job=False)  # anonymous: refused
    rec = A.save("Acme - SWE", q, "Yes", profile=str(bank), workspace=str(bank), requeue_job=False, by="shadow")
    assert "job-scoped" in rec["source"]
    kept = json.load(open(bank / "q" / "job_extra.json"))
    assert kept["Acme - SWE"][A.pattern_for(q)] == "Yes"  # on that job only, exactly like the user's own answer
    with pytest.raises(ValueError):  # EEO stays decline-only, for the user and Shadow alike
        A.save("Acme - SWE", "What is your gender?", "Male", profile=str(bank), workspace=str(bank), by="shadow")


def test_shadow_open_answer_goes_to_the_bank(bank):
    rec = A.save("Acme - SWE", "Have you built an LLM workflow?", "Yes", profile=str(bank), workspace=str(bank),
                 requeue_job=False, by="shadow")
    assert rec["source"].startswith("shadow")
    assert json.load(open(bank / "answers.json"))[0]["answer"] == "Yes"


# ---- the two-call handoff (engine/shadow.py) ----
import time as _t
from engine import shadow as S


@pytest.fixture
def board(tmp_path, monkeypatch):
    evs = {"application": [], "answer": [], "answer_queued": [], "shadow": []}
    monkeypatch.setattr(O, "PATH", str(tmp_path / "override.json"))
    monkeypatch.setattr(S, "CALLS", str(tmp_path / "calls.json"))
    monkeypatch.setattr("engine.feedback.events.read", lambda kind: list(evs.get(kind, [])))
    monkeypatch.setattr("engine.feedback.events.record", lambda kind, **k: evs.setdefault(kind, []).append(k))
    retried = []
    monkeypatch.setattr(S, "_retry_as_shadow", lambda jobs: retried.extend(jobs) or len(jobs))
    monkeypatch.setattr(S, "MEMORY", str(tmp_path / "shadow_memory.json"))
    monkeypatch.setattr("engine.config.PROFILE", str(tmp_path))
    saved = []
    monkeypatch.setattr("engine.feedback.answers.save", lambda job, q, a, **k: saved.append((job, q, a, k.get("by"))))
    monkeypatch.setattr(S, "recommend", lambda q, job="": {"q": q, "a": "No" if "used" in q else None, "from": "Fact Bank draft"})
    evs["saved"] = saved
    S.configure("calls", 5)
    return evs, retried


def _park(evs, job, detail="NEEDS YOU: Desired Salary", ago=60):
    ts = _t.strftime("%Y-%m-%dT%H:%M:%S", _t.localtime(_t.time() - ago))
    evs["application"].append({"ts": ts, "job": job, "url": "u/" + job, "status": "NEEDS YOU", "detail": detail})


def test_two_calls_then_shadow_picks_up(board):
    evs, retried = board
    _park(evs, "Acme - SWE")
    now = _t.time()
    assert S.tick(now)["call1"] == 1
    assert S.tick(now + 60) == {"call1": 0, "call2": 0, "shadow": 0, "you": 0}   # still ringing call 1
    assert S.tick(now + 5 * 60)["call2"] == 1
    assert S.tick(now + 10 * 60)["shadow"] == 1 and retried == ["Acme - SWE"]
    assert S.tick(now + 20 * 60)["shadow"] == 0  # picked up once, never again


def test_you_pick_up_by_answering(board):
    evs, retried = board
    _park(evs, "Acme - SWE")
    now = _t.time()
    S.tick(now)
    evs["answer_queued"].append({"ts": _t.strftime("%Y-%m-%dT%H:%M:%S", _t.localtime(now + 30)), "job": "Acme - SWE"})
    assert S.tick(now + 60)["you"] == 1
    S.tick(now + 30 * 60)
    assert retried == []


def test_human_checks_and_old_parks_never_ring(board):
    evs, _ = board
    _park(evs, "Bot - SWE", detail="NEEDS YOU: please complete the captcha")
    _park(evs, "Old - SWE", ago=3 * 24 * 3600)
    assert S.tick()["call1"] == 0


def test_off_mode_rings_but_never_picks_up(board):
    evs, retried = board
    S.configure("off")
    _park(evs, "Acme - SWE")
    now = _t.time()
    S.tick(now); S.tick(now + 300); S.tick(now + 600)
    assert retried == [] and S.status(now + 600)["ringing"] == 1


def test_manual_pickup_hands_to_shadow(board):
    evs, retried = board
    _park(evs, "Acme - SWE")
    S.tick()
    S.pickup("u/Acme - SWE", "shadow")
    assert retried == ["Acme - SWE"] and S.status()["by_shadow"] == 1


def test_recommends_at_call1_and_uses_it_when_nobody_answers(board):
    evs, retried = board
    _park(evs, "Acme - SWE", detail="NEEDS YOU: Have you used Foo before? | Describe a hobby")
    now = _t.time()
    S.tick(now)
    line = S.lines(now)[0]
    assert [r["a"] for r in line["recommend"]] == ["No", None]  # nothing on file for the hobby: no invented answer
    S.tick(now + 300); S.tick(now + 600)
    assert evs["saved"] == [("Acme - SWE", "Have you used Foo before?", "No", "shadow")]
    mem = json.load(open(S.MEMORY))
    assert list(mem.values())[0]["answer"] == "No" and list(mem.values())[0]["by"] == "shadow"


def test_your_answer_overrides_shadow_memory_and_learning_counts(board, tmp_path):
    evs, _ = board
    S.remember("Have you used Foo before?", "No", "shadow", "Acme - SWE")
    S.remember("Have you used Foo before?", "Yes", "you", "Acme - SWE")
    S.remember("Have you used Foo before?", "No", "shadow", "Beta - SWE")  # Shadow never overwrites you
    e = list(json.load(open(S.MEMORY)).values())[0]
    assert e["answer"] == "Yes" and e["by"] == "you" and e["overridden"] == 1
    evs["application"].append({"ts": "2026-11-06T22:00:00", "job": "Acme - SWE", "status": "SUBMITTED"})
    evs["outcome"] = [{"outcome": "interview", "jobs": ["Acme - SWE"]}]
    S.learn()
    e = list(json.load(open(S.MEMORY)).values())[0]
    assert e["submitted"] == 1 and e["moved_forward"] == 1
