"""Shadow's brain, ownership ladder and agent graph (11-07)."""
from engine import agents, shadow_brain as B


def test_answers_compare_by_meaning_not_spelling():
    assert B.same_answer("US", "United States")
    assert B.same_answer("masters", "Master's degree")
    assert B.same_answer("__ACK__", "I agree")
    assert B.same_answer("Careers Website", "Company website")
    assert B.same_answer("Yes, I can", "yes")
    assert not B.same_answer("Yes", "No")
    assert not B.same_answer("Springfield, IL", "United States")


def test_unescape_keeps_only_plain_questions():
    import re
    assert B.unescape(re.escape("are you open to relocation?")) == "are you open to relocation?"
    assert B.unescape(r"relocat(e|ion)|move") is None


def test_split_is_fixed_and_roughly_80_20():
    qs = [f"question number {i} about work" for i in range(500)]
    assert [B.split_of(q) for q in qs] == [B.split_of(q) for q in qs]
    test = sum(B.split_of(q) == "test" for q in qs)
    assert 60 < test < 140


POL = {"tau": 0.6, "sigma": 0.8, "reliability": {s: [8, 2] for s in B.STRATEGIES}, "context": {}}


def test_agreeing_strategies_vote_together_noisy_or():
    alone = B.choose([("engine", "Yes", 0.7)], POL)
    together = B.choose([("engine", "Yes", 0.7), ("yesno", "yes", 0.6)], POL)
    assert alone[0] is None and together[0] == "Yes" and together[1] > alone[1]


def test_abstains_when_unsure_and_ignores_weak_neighbours():
    assert B.choose([("neighbor", "No", 0.79)], POL)[0] is None  # below sigma: not even a candidate
    assert B.choose([("bank", "No", 1.0)], POL) == ("No", 0.8, "bank")


def test_contextual_reliability_shrinks_toward_the_strategy():
    pol = {**POL, "context": {"engine:yesno": [0, 20]}}
    assert B.rel_for(pol, "engine", "Do you have 3 years of Go?") < 0.2
    assert B.rel_for(pol, "engine", "What is your name?") == 0.8


def test_shape_check_penalises_paragraphs_and_bare_yes_no():
    assert B.shape("Are you local to Ann Arbor, MI?", "x" * 200) < 1
    assert B.shape("What percentage of the time are you willing to travel?", "Yes") < 1
    assert B.shape("Are you open to relocation?", "Yes") == 1


def test_blocked_questions_get_no_candidates_ever():
    assert B.candidates("Please complete the captcha below") == []
    assert B.candidates("Are you a robot?") == []


def test_ladder_climbs_only_with_evidence():
    rec = {"test_n": 0, "test_precision": 0, "violations": 0, "live_answers": 0, "override_rate": 0,
           "shadow_submitted": 0, "clean_days": 0, "trained": None}
    assert B.ladder(rec)["level"] == 1
    rec.update(trained="now", test_n=25, test_precision=0.92)
    assert B.ladder(rec)["level"] == 2
    rec.update(violations=1)
    assert B.ladder(rec)["level"] == 1  # one truthfulness violation drops every earned rung
    rec.update(violations=0, test_n=200, test_precision=0.99, live_answers=500, override_rate=0.01,
               shadow_submitted=200, clean_days=40)
    assert B.ladder(rec)["level"] == 5
    rec.update(clean_days=3)
    assert B.ladder(rec)["level"] == 3


def test_shadow_balance_never_swaps_the_host():
    assert agents.shadow_want(1, 7, jobs=30) == 7
    assert agents.shadow_want(1, 7, jobs=30, mem_mb=5500) == 1  # 600 MB left: one applier, never more
    assert agents.shadow_want(1, 7, jobs=2, mem_mb=1000) == 1


FLEET = {"members": [{"role": "applier", "host": "abc123def", "up": True, "state": "watching", "batch": None},
                     {"role": "applier", "host": "dead00", "up": False},
                     {"role": "supervisor", "up": True, "services": {"api": "ok", "web": "ok"}},
                     {"role": "pipeline", "up": True, "state": "scanning boards"}],
         "stale_claims": ["b1.json"]}
LINES = [{"url": "u1", "job": "Acme - SWE", "open": True, "state": "call 1",
          "recommend": [{"q": "Open to relocation?", "a": "Yes", "conf": 0.9, "strategy": "bank"}]},
         {"url": "u2", "job": "Beta - SWE", "open": True, "state": "call 2",
          "recommend": [{"q": "Experience with Beta?", "a": None}]}]


def test_agent_graph_nests_and_marks_owners(monkeypatch):
    monkeypatch.setattr("engine.shadow.settings", lambda: {"mode": "autopilot", "ring_min": 5})
    g = agents.graph(FLEET, LINES, level=1)
    c = agents.count(g)
    assert c["shadow"] == 1 and c["applier"] == 1 and c["job"] == 2 and c["question"] == 2 and c["service"] == 3
    groups = {n["label"]: n for n in g["children"]}
    assert groups["Applier agents"]["owner"] == "supervisor" and groups["Parked jobs"]["owner"] == "shadow"
    assert agents.graph(FLEET, LINES, level=3)["children"][0]["owner"] == "shadow"


def test_plan_locks_actions_above_the_earned_level():
    p = agents.plan(FLEET, LINES, level=1)
    retry = [a for a in p if a["action"] == "retry"]
    assert [a["target"] for a in retry] == ["Acme - SWE"]  # Beta has a question Shadow abstains on
    assert all(not a["allowed"] for a in p)
    assert all(a["allowed"] for a in agents.plan(FLEET, LINES, level=2) if a["needs_level"] <= 2)


def test_autopilot_mode_answers_inline(tmp_path, monkeypatch):
    from engine import override, shadow
    monkeypatch.setattr(override, "PATH", str(tmp_path / "override.json"))
    monkeypatch.setattr("engine.feedback.events.record", lambda *a, **k: None)
    s = shadow.configure("autopilot")
    assert s["mode"] == "autopilot" and override.on()


def test_decide_abstains_on_form_helper_text(monkeypatch):
    """11-11: a Greenhouse helper string came back as Shadow's answer to a select question; it must abstain."""
    from engine import shadow_brain as B
    monkeypatch.setattr(B, "candidates", lambda q, job="", k=None: [])
    monkeypatch.setattr(B, "choose", lambda c, pol=None, question=None: ("Draft an ideal answer with this", 0.9, "engine"))
    r = B.decide("How would you describe your experience with Acme? (Select one)")
    assert r["a"] is None and r["conf"] == 0.0
