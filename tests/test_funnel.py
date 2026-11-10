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


def test_funnel_splits_and_unrecorded_values():
    import re as _re
    apps = [{"job": f"Big{i} - Engineer", "url": f"u{i}", "ts": "2026-11-09T12:00:00"} for i in range(4)] + \
           [{"job": f"Small{i} - Engineer", "url": f"s{i}", "ts": "2026-11-09T12:00:00", "answered_by": "shadow"}
            for i in range(6)]
    outs = {"Big0 - Engineer": {"oa"}, "Big1 - Engineer": {"interview", "oa"}, "Small0 - Engineer": {"rejection"}}
    resumes = {"u0": {"lane": "backend", "ats": "greenhouse", "posted": "2026-11-09T09:00:00", "keywords_on": True},
               "u1": {"lane": "backend", "posted": "2026-11-08T00:00:00", "jd_keywords": []},
               "s0": {"lane": "ai", "posted": "2026-11-01T00:00:00Z"}}
    f = funnel.funnel(apps, outs, resumes, tiers={"tier1": _re.compile("big", _re.I)}, drafted={"small1"})
    o = f["overall"]
    assert (o["verified"], o["replied"], o["oa"], o["interview"], o["positive"]) == (10, 3, 2, 1, 2)
    rows = {dim: {g: c for g, c, _, _ in r} for dim, r in f["splits"].items()}
    assert set(rows) == set(funnel.DIMENSIONS)
    assert rows["tier"]["tier1"]["positive"] == 2 and rows["tier"]["other"]["verified"] == 6
    assert rows["posting age"]["<6h"]["verified"] == 1 and rows["posting age"]["6-48h"]["verified"] == 1
    assert rows["posting age"][">48h"]["verified"] == 1 and rows["posting age"]["not recorded"]["verified"] == 7
    assert rows["role keywords"]["on"]["verified"] == 1 and rows["role keywords"]["off"]["verified"] == 1
    assert rows["answered by"]["shadow"]["verified"] == 6 and rows["answered by"]["not recorded"]["verified"] == 4
    assert rows["outreach"]["drafted"]["verified"] == 1
    assert rows["ats"]["greenhouse"]["verified"] == 1 and rows["ats"]["other"]["verified"] == 9


def test_funnel_says_not_significant_when_it_is_not(capsys):
    apps = [{"job": f"Co{i} - E", "url": f"u{i}"} for i in range(40)]
    outs = {"Co0 - E": {"oa"}, "Co20 - E": {"oa"}}
    resumes = {f"u{i}": {"lane": "a" if i < 20 else "b"} for i in range(40)}
    f = funnel.funnel(apps, outs, resumes, tiers={}, drafted=set())
    assert not any(sig for rows in f["splits"].values() for *_, sig in rows)
    funnel.print_funnel(f)
    assert "counts, not findings" in capsys.readouterr().out


def test_one_positive_mail_matched_to_many_roles_counts_once():
    """11-09 hand-check: one employer's assessment mail tied to 6 roles was read as 5 OAs."""
    ev = [{"outcome": "oa", "jobs": ["Acme - Role A"]},
          {"outcome": "oa", "jobs": ["Acme - Role A", "Acme - Role B", "Acme - Role C"]},
          {"outcome": "oa", "jobs": ["Acme - Role B", "Acme - Role C"]},   # later mail names another role first
          {"outcome": "rejection", "jobs": ["Acme - Role B", "Acme - Role C"]}]
    outs = funnel.outcomes(ev)
    assert outs["Acme - Role A"] == {"oa"}
    assert outs["Acme - Role B"] == {"rejection"} and outs["Acme - Role C"] == {"rejection"}
    r = funnel.rate([{"job": f"Acme - Role {c}"} for c in "ABC"], outs)
    assert r["oa"] == 1 and r["positive"] == 1


def test_positive_is_credited_to_a_verified_role_when_there_is_one():
    ev = [{"outcome": "oa", "jobs": ["Acme - Unverified"]},
          {"outcome": "oa", "jobs": ["Acme - Unverified", "Acme - Verified", "Acme - Other"]}]
    outs = funnel.outcomes(ev, prefer={"Acme - Verified", "Acme - Other"})
    assert outs["Acme - Verified"] == {"oa"} and "Acme - Other" not in outs
    assert funnel.rate([{"job": "Acme - Verified"}, {"job": "Acme - Other"}], outs)["oa"] == 1
