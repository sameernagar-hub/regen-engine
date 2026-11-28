"""11-28 filler gaps: places autocomplete picks, decline/ack wording, degree-year buckets, LGB question."""
import engine.apply.runner as r


C, ST, S = r.P["city"], r.P["state_abbr"], r.P["state"]


def opts(*t):
    return [(x, x) for x in t]


def test_location_option_takes_home_city_in_state():
    o = opts(f"{C}, Costa Rica", f"{C}, {ST}, USA", f"{C}, {S}, United States")
    assert r.location_option(o, f"{C}, {ST}, United States") == f"{C}, {ST}, USA"


def test_location_option_never_another_city_or_country():
    me = f"{C}, {ST}, United States"
    assert r.location_option(opts(f"{C}, Costa Rica", f"{C} del Monte, Philippines"), me) is None
    assert r.location_option(opts(f"{C}, Illinois, United States"), me) is None
    assert r.location_option([], me) is None


def test_location_option_state_level_fallback():
    assert r.location_option(opts("Berlin, Germany", f"{S}, United States"), f"{C}, {ST}, United States") == f"{S}, United States"


def test_decline_wordings():
    for t in ("I don't wish to answer", "Decline to self-identify", "I would rather not say", "Prefer not to disclose", "I do not want to answer"):
        assert r.pick_option([("Yes", 1), ("No", 2), (t, 3)], "__DECLINE__") == 3, t


def test_decline_never_picks_a_fact():
    assert r.pick_option(opts("Yes", "No"), "__DECLINE__") is None


def test_attest_checkbox_wordings():
    assert r.pick_option(opts("I certify that the above is true"), "__ACK__")
    assert r.pick_option(opts("I affirm the information is accurate"), "__ACK__")
    assert r.pick_option(opts("I do not agree"), "__ACK__") is None


def test_degree_year_buckets():
    assert r.pick_option(opts("2020", "2021", "2022", "2023"), "2022") == "2022"
    assert r.pick_option(opts("2023 or later", "2022 or earlier"), "2021") == "2022 or earlier"
    assert r.pick_option(opts("Before 2021", "2021-2023", "After 2023"), "2022") == "2021-2023"
    assert r.pick_option(opts("2023", "2024"), "2022") is None  # never another year


def test_lgb_and_bachelor_completion_questions_answered():
    assert r.answer_for("Do you consider yourself a member of the Lesbian, Gay or Bisexual (LGB) community?", {}) == "__DECLINE__"
    q = "When did you complete, or when do you expect to complete, your bachelor’s degree requirements?"
    assert r.answer_for(q, {}) == r.undergrad_year()
