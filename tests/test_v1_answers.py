"""v1 release review: answers that went wrong on real forms on 10-17 (parked, not submitted), now pinned."""
from engine.apply.runner import P, answer_for


def test_country_to_work_in_is_a_country():
    q = "Please enter the country you are legally registered to work in."
    assert answer_for(q, {}) == P["country"]
    assert answer_for("Which country are you authorized to work in?", {}) == P["country"]


def test_describe_years_is_not_a_bare_number():
    q = "Describe your experience with Amazon EC2 and Debian Linux. Include key responsibilities and years of experience."
    assert answer_for(q, {}) != P["years_experience"]
    assert answer_for("How many years of professional experience do you have?", {}) == P["years_experience"]


def test_product_names_are_not_link_boxes():
    q = ("Which best describes your experience using AI coding agents (such as Cursor, Claude Code, or GitHub Copilot) "
         "in your software development workflow?")
    assert answer_for(q, {}) != P["github"]
    assert answer_for("GitHub URL", {}) == P["github"]
    assert answer_for("Website", {}) == P["github"]
    assert answer_for("LinkedIn Profile", {}) == P["linkedin"]
