"""The agent orchestrator (engine/orchestrator.py): scheduling, dedupe, ladder gating, budgets, retries, leases."""
import time

import engine.orchestrator as O


def at(h, d=23):
    return time.mktime((2026, 11, d, h, 0, 0, 0, 0, -1))


def fns(log, fail=False):
    def run(payload):
        log.append(payload)
        if fail:
            raise RuntimeError("boom")
        return "ok"
    return {"shadow_retry": run, "requeue_batch": run}


def only(monkeypatch, *names):
    monkeypatch.setattr(O, "REGISTRY", {n: O.REGISTRY[n] for n in names})


def test_plan_retry_runs_only_at_level_two_and_is_deduped(tmp_path, monkeypatch):
    only(monkeypatch, "shadow_retry")
    path, ran = str(tmp_path / "s.json"), []
    plan = [{"action": "retry", "target": "Acme - SWE"}]
    s = O.tick(plan=plan, level=1, fns=fns(ran), path=path, now=at(9))
    t = next(iter(s["tasks"].values()))
    assert t["state"] == "held" and "level 2" in t["held"] and not ran  # locked by the ladder: shown, never run
    s = O.tick(plan=plan, level=2, fns=fns(ran), path=path, now=at(9) + 15)
    assert ran == [{"target": "Acme - SWE", "why": None}] and len(s["tasks"]) == 1
    O.tick(plan=plan, level=2, fns=fns(ran), path=path, now=at(9) + 30)
    assert len(ran) == 1  # cooldown: the runner gets time before the same retry is queued again
    O.tick(plan=plan, level=2, fns=fns(ran), path=path, now=at(9) + O.PLAN_COOLDOWN + 60)
    assert len(ran) == 2


def test_plan_task_dropped_when_it_leaves_the_plan(tmp_path, monkeypatch):
    only(monkeypatch, "shadow_retry")
    path = str(tmp_path / "s.json")
    O.tick(plan=[{"action": "retry", "target": "X"}], level=1, fns=fns([]), path=path, now=at(9))
    s = O.tick(plan=[], level=1, fns=fns([]), path=path, now=at(9) + 15)
    assert s["tasks"] == {}


def test_scale_actions_stay_with_the_governor(tmp_path, monkeypatch):
    only(monkeypatch, "shadow_retry")
    s = O.tick(plan=[{"action": "scale", "target": "appliers 1 -> 3"}], level=5, fns=fns([]),
               path=str(tmp_path / "s.json"), now=at(9))
    assert s["tasks"] == {}


def test_failures_back_off_then_dead_letter(tmp_path, monkeypatch):
    only(monkeypatch, "shadow_retry")
    path, ran = str(tmp_path / "s.json"), []
    plan = [{"action": "retry", "target": "J"}]
    s = O.tick(plan=plan, level=2, fns=fns(ran, fail=True), path=path, now=at(9))
    t = next(iter(s["tasks"].values()))
    assert t["state"] == "queued" and t["not_before"] > at(9) and t["attempts"] == 1
    s = O.tick(plan=plan, level=2, fns=fns(ran, fail=True), path=path, now=at(9) + 10)
    assert len(ran) == 1  # backing off
    s = O.tick(plan=plan, level=2, fns=fns(ran, fail=True), path=path, now=at(9) + 120)
    t = next(iter(s["tasks"].values()))
    assert t["state"] == "failed" and t["attempts"] == 2 and "boom" in t["last_error"]


def test_daily_agents_wait_for_hour_and_chain(tmp_path, monkeypatch):
    only(monkeypatch, "hn", "outreach", "outreach_gmail")
    path = str(tmp_path / "s.json")
    s = O.load(path)
    O.schedule(s, at(O.DAILY_HOUR - 1), imap=True)
    assert s["tasks"] == {}
    O.schedule(s, at(O.DAILY_HOUR), imap=True)
    assert [t["agent"] for t in s["tasks"].values()] == ["hn"]  # outreach waits for today's hn
    O.schedule(s, at(O.DAILY_HOUR) + 60, imap=True)
    assert len(s["tasks"]) == 1  # once a day
    s["agents"]["hn"]["day_done"] = O._day(at(O.DAILY_HOUR))
    O.schedule(s, at(O.DAILY_HOUR) + 120, imap=False)
    assert sorted(t["agent"] for t in s["tasks"].values()) == ["hn", "outreach"]  # no IMAP: no Gmail drafts


def test_kill_pause_and_budget_hold_tasks(tmp_path, monkeypatch):
    only(monkeypatch, "shadow_retry")
    monkeypatch.setattr(O, "WORKSPACE", str(tmp_path))
    s, now = O.load(str(tmp_path / "s.json")), at(9)
    t = O.enqueue(s, "shadow_retry", payload={"target": "J"}, now=now)
    (tmp_path / "KILL").write_text("test")
    assert O.blocked(s, t, 5, now) == "kill switch on"
    (tmp_path / "KILL").unlink()
    s["agents"]["shadow_retry"] = {"paused": True}
    assert O.blocked(s, t, 5, now) == "paused by operator"
    s["agents"]["shadow_retry"] = {"paused": False, "runs_day": O._day(now), "runs": O.REGISTRY["shadow_retry"]["budget"]}
    assert "budget" in O.blocked(s, t, 5, now)


def test_lost_proc_lease_is_requeued(tmp_path):
    s, now = {"tasks": {}, "agents": {}}, at(9)
    t = O.enqueue(s, "learn", now=now)
    t.update(state="leased", kind="proc", attempts=1, lease_until=now + 600)
    O.reap(s, now + 5)  # no child in this process: the supervisor restarted
    assert t["state"] == "queued" and "lost" in t["last_error"]


def test_command_is_a_request_the_tick_applies(tmp_path, monkeypatch):
    only(monkeypatch, "learn")
    path, reqs = str(tmp_path / "s.json"), str(tmp_path / "requests")
    out = O.command("pause", "learn", reqs=reqs)
    assert out["request"] and O.load(path)["tasks"] == {}  # nothing written to the state by the caller
    O.command("run", "learn", reqs=reqs)
    s = O.tick(plan=[], level=1, path=path, now=at(9))
    assert s["agents"]["learn"]["paused"] is True
    assert any(t["by"] == "operator" and t["state"] == "held" for t in s["tasks"].values())  # queued, held by the pause
    import os, pytest
    assert not [f for f in os.listdir(reqs) if f.endswith(".json")]  # consumed
    with pytest.raises(ValueError):
        O.command("run", "rm-rf", reqs=reqs)
    with pytest.raises(ValueError):
        O.command("delete", "learn", reqs=reqs)
