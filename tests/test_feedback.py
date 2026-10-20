"""Rejection feedback loop: phrase scoring, Fact-Bank exclusion, user off-switch, and the fit gate reading it."""
import json, os

from engine.feedback import rejections as R


def _corpus():
    texts, lab = {}, []
    for i in range(6):  # rejected: all ask for clinical data experience
        texts[f"u{i}"] = "requirements: experience with clinical trials data pipelines and python required."
        lab.append((f"j{i}", f"u{i}", "rejection"))
    for i in range(6, 12):  # the rest: plain python roles, no reply yet
        texts[f"u{i}"] = "requirements: experience building python services and apis required."
        lab.append((f"j{i}", f"u{i}", "pending"))
    return texts, lab


def test_grams_only_requirement_sentences():
    g = R.grams("we offer great snacks and free lunch. you have experience with kafka streams.")
    assert "kafka streams" in g and not any("snacks" in x for x in g)


def test_analyze_learns_rejected_phrase_not_fact_bank_skill():
    texts, lab = _corpus()
    rules, stats = R.analyze(texts, lab, vocab={"python", "apis"})
    phrases = {r["phrase"] for r in rules}
    assert any("clinical" in p for p in phrases)
    assert not any("python" in p for p in phrases)
    assert stats["rejected"] == 6 and stats["baseline_rejection_rate"] == 0.5


def test_positive_outcome_vetoes_a_phrase():
    texts, lab = _corpus()
    lab[6] = ("j6", "u6", "positive")
    texts["u6"] = "requirements: experience with clinical trials data pipelines required."
    rules, _ = R.analyze(texts, lab, vocab={"python"})
    assert not any("clinical" in r["phrase"] for r in rules)


def test_too_few_rejections_learn_nothing():
    texts, lab = _corpus()
    rules, _ = R.analyze(texts, lab[2:], vocab={"python"})  # 4 rejected still enough
    assert rules
    rules, _ = R.analyze(texts, lab[3:], vocab={"python"})  # 3 rejected: below MIN_REJ
    assert not rules


def test_user_off_survives_and_fit_reads_active(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "GATE", str(tmp_path / "learned_gate.json"))
    rules = [{"phrase": "clinical trials", "rejected": 5, "seen": 5, "evidence": "significant"},
             {"phrase": "kafka streams", "rejected": 4, "seen": 4, "evidence": "significant"},
             {"phrase": "problem solving", "rejected": 6, "seen": 10, "evidence": "weak"}]
    R.save_gate([dict(r) for r in rules], {})
    R.turn_off("kafka streams")
    gate = R.save_gate([dict(r) for r in rules], {})
    status = {r["phrase"]: r["status"] for r in gate["rules"]}
    assert status == {"clinical trials": "active", "kafka streams": "off", "problem solving": "proposed"}

    from engine.tailoring import tailor
    monkeypatch.setattr("engine.config.WORKSPACE", str(tmp_path))
    tailor._LEARNED["mtime"] = None
    assert tailor.learned_phrases() == ("clinical trials",)
    assert "learned: clinical trials" in tailor.fit("You have experience with clinical trials.", max_years=3)
    assert not [b for b in tailor.fit("You have kafka streams experience.", max_years=3) if b.startswith("learned")]


def test_boilerplate_with_small_samples_stays_proposed():
    """10-19 first pass: 6 of 10 at a 0.28 baseline looked like signal; corrected for 1000s of phrases it is not."""
    assert R.tail(6, 10, 0.28) * 1000 > R.ALPHA
    assert R.tail(20, 20, 0.28) * 1000 < R.ALPHA


def test_gearbox_sets_appliers_loop_and_clutch(tmp_path, monkeypatch):
    from engine import gearbox as G, supervisor as S
    from engine.tailoring import tailor
    monkeypatch.setattr(G, "PATH", str(tmp_path / "gear.json"))
    monkeypatch.setattr("engine.feedback.events.record", lambda *a, **k: {})
    assert G.appliers() is None and G.loop_minutes(3) == 3  # no gear yet: the env / --scale decide
    G.shift("4")
    assert S.limits(1, 1) == (2, 9) and G.loop_minutes(3) == 2
    G.shift("n")
    assert S.limits(1, 5) == (0, 0) and G.loop_minutes(3) is None
    try:
        G.shift("9")
        assert False
    except ValueError:
        pass
    (tmp_path / "learned_gate.json").write_text('{"rules": [{"phrase": "clinical trials", "status": "active"}]}')
    monkeypatch.setattr("engine.config.WORKSPACE", str(tmp_path))
    tailor._LEARNED["mtime"] = None
    assert tailor.learned_phrases() == ("clinical trials",)
    G.shift(clutch="off")
    assert tailor.learned_phrases() == ()


def test_automotive_design_release_is_not_software():
    """10-19 mis-submit: "Underhood Trim Design Release Engineer" matched the build/release include titles."""
    import re
    from engine.discovery.filters import keep
    dom = {"include_titles": re.compile(r"release engineer|software", re.I), "exclude_titles": re.compile(r"$^"),
           "require_us": True}
    assert keep(dom, "Underhood Trim Design Release Engineer", "Detroit, MI") == "non-software discipline"
    assert keep(dom, "Powertrain Design Release Engineer", "Detroit, MI") == "non-software discipline"
    assert keep(dom, "Software Release Engineer", "Seattle, WA") is None
