"""11-12: generic words must not count as technologies (they inflated coverage and put cert titles in headlines)."""
from engine.tailoring import keywords, tailor


def test_generic_words_are_not_tech():
    for w in ("service", "field", "code", "review", "power", "process", "advanced", "administrator", "search"):
        assert not tailor._tech_word(w), w


def test_real_tech_words_stay():
    for w in ("kafka", "spring", "eks", "python", "kubernetes", "react", "msk"):
        assert tailor._tech_word(w), w


def test_headings_and_states_are_not_toolish():
    jd = "KEY DUTIES: build services in Minneapolis, MN. A DAY IN THE LIFE. Uses GraphQL, SQS and OpenSearch."
    got = keywords._toolish(jd)
    assert not {"KEY", "DUTIES", "DAY", "MN"} & set(got)
    assert "SQS" in got and "OpenSearch" in got


def test_reject_reason_and_level_rank():
    from engine.feedback.inbox import reject_reason
    from engine import targeting
    assert reject_reason("we are unable to sponsor a visa for this role") == "sponsorship"
    assert reject_reason("the position has been filled") == "position closed"
    assert reject_reason("we decided to move forward with other candidates") == "volume / other candidates"
    assert reject_reason("thanks for applying") == "unstated"
    assert targeting.level_rank({"title": "Software Engineer II"}) == 1
    assert targeting.level_rank({"title": "Software Engineer, New Grad"}) == 0


def test_proof_file_accepts_text_sibling(tmp_path, monkeypatch):
    import engine.config as c
    monkeypatch.setattr(c, "WORKSPACE", str(tmp_path))
    (tmp_path / "proof").mkdir()
    (tmp_path / "proof" / "a.txt").write_text("x")
    assert c.proof_file("proof/a.png") and c.proof_file("proof/a.txt") and not c.proof_file("proof/b.png")
