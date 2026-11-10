"""Interview rate (docs/NEXT_STEPS.md §1.2): the number shown beside every volume figure, and its interval."""
import os
import re

from engine.feedback import funnel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_wilson_interval():
    assert funnel.wilson(0, 0) == (0.0, 0.0)
    lo, hi = funnel.wilson(0, 400)          # zero successes still has an upper bound above zero
    assert lo == 0.0 and 0.005 < hi < 0.015
    lo, hi = funnel.wilson(50, 100)         # textbook value: 0.404 to 0.596
    assert abs(lo - 0.404) < 0.002 and abs(hi - 0.596) < 0.002
    lo, hi = funnel.wilson(6, 426)
    assert lo < 6 / 426 < hi and 0 <= lo and hi <= 1
    assert funnel.wilson(10, 10)[1] == 1.0


def test_rate_counts_each_application_once():
    apps = [{"job": f"Co{i} - Engineer"} for i in range(10)]
    outs = {"Co0 - Engineer": {"confirmation", "oa", "interview"},   # one application, two positives: counted once
            "Co1 - Engineer": {"oa"},
            "Co2 - Engineer": {"rejection", "confirmation"},
            "Co3 - Engineer": {"confirmation"},
            "Someone Else - Role": {"interview"}}                    # not a verified application: ignored
    r = funnel.rate(apps, outs)
    assert (r["verified"], r["oa"], r["interview"], r["offer"], r["positive"]) == (10, 2, 1, 0, 2)
    assert r["rejection"] == 1 and r["no_reply"] == 7
    assert r["per_100"] == 20.0
    lo, hi = r["interval_per_100"]
    assert lo < 20.0 < hi
    assert "20.0 per 100" in funnel.line(r) and "95% interval" in funnel.line(r)


def test_rate_with_nothing_sent():
    r = funnel.rate([], {})
    assert r["verified"] == 0 and r["per_100"] == 0.0 and r["interval_per_100"] == (0.0, 0.0)


def test_readme_shows_the_rate_beside_applications_sent():
    """NEXT_STEPS §1.2: 'applications sent' never appears without the interview rate and its reproduce command."""
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    assert "applications sent with proof" in readme
    row = next(l for l in readme.splitlines() if "applications sent with proof" in l)
    assert re.search(r"per 100", row), "the stats row must carry the interview / OA rate"
    assert "python -m engine report rate" in readme
