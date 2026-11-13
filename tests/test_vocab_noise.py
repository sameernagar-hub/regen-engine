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
