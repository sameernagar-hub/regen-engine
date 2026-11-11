"""The README's "Never bluffs" row and the code must agree (docs/NEXT_STEPS.md §1.1, user decision 11-07: option a).

The claim: every resume line comes from the Fact Bank and a validator rejects anything else. The "Role Keywords" line
(engine/tailoring/keywords.py) prints posting terms the Fact Bank lacks, which resume.validate() cannot check, so the
claim is true only while that line is off by default. These tests fail if either side moves without the other.
"""
import json
import os
import re

import pytest

from engine.tailoring import keywords, resume
from engine.tailoring.tailor import tailor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAIM = "Every resume line comes from your Fact Bank"
JD = "We use Kafka, Kubernetes, React, PostgreSQL, Haskell and Elixir every day."
SENTINEL = "Zzqxsentinel"

# Spec keys whose text reaches the PDF, and what vouches for each. A new key read by resume.build() must be added to
# one of these on purpose (and to validate() if it carries free text), or test_build_reads_only_vouched_keys fails.
VALIDATED = {"roles", "projects", "skills", "skill_text", "fact_pick"}   # checked against the bank by validate()
COMPOSED = {"headline", "summary", "projects_title"}                     # written by compose.py (tests/test_compose.py)
FLAGGED = {"jd_keywords"}                                                # printed only with REGEN_JD_KEYWORDS=1
PLUMBING = {"file", "url"}  # url: never printed, only picks the Role Keywords A/B arm (keywords.enabled(url))


def _lane():
    lanes = json.load(open(os.path.join(ROOT, "profile.example", "lanes.json"), encoding="utf-8"))
    return dict(lanes["lanes"][lanes["default"]], file="truth_claims_test.pdf")


class _Spy(dict):
    """A spec that remembers which keys were read."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.read = set()

    def __getitem__(self, k):
        self.read.add(k)
        return super().__getitem__(k)

    def get(self, k, default=None):
        self.read.add(k)
        return super().get(k, default)


def _story_text(spec, monkeypatch):
    """Every text block resume.build() hands to the PDF, as plain text (table cells included)."""
    got = []

    class Doc:
        def __init__(self, *a, **k):
            pass

        def build(self, story):
            got.extend(story)

    monkeypatch.setattr(resume, "SimpleDocTemplate", Doc)
    resume.build(spec)
    out = []
    for item in got:
        cells = [c for r in getattr(item, "_cellvalues", []) for c in r] or [item]
        out += [c.getPlainText() for c in cells if hasattr(c, "getPlainText")]
    return out


def test_role_keywords_default_matches_the_readme(monkeypatch):
    monkeypatch.delenv("REGEN_JD_KEYWORDS", raising=False)
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    claims = CLAIM in readme
    assert claims == (not keywords.enabled()), (
        "README 'Never bluffs' and the REGEN_JD_KEYWORDS default disagree: the claim is true only while the Role "
        "Keywords line is off by default (docs/NEXT_STEPS.md §1.1)")
    assert keywords.DEFAULT == "0" and not keywords.enabled()


def test_flag_off_no_posting_terms_reach_the_resume(monkeypatch):
    monkeypatch.delenv("REGEN_JD_KEYWORDS", raising=False)
    out = tailor(_lane(), JD)
    assert "jd_keywords" not in out
    resume.validate(out)
    # a spec saved while the flag was on (a retry rebuilding its PDF) must not print the line either
    text = _story_text(dict(out, jd_keywords=[SENTINEL]), monkeypatch)
    assert not any(SENTINEL in t or "Role Keywords" in t for t in text)


def test_flag_on_keeps_the_feature(monkeypatch):
    """Nothing was deleted: REGEN_JD_KEYWORDS=1 brings the line back, listed apart and recorded in the spec."""
    monkeypatch.setenv("REGEN_JD_KEYWORDS", "1")
    out = tailor(_lane(), JD)
    assert out.get("jd_keywords"), "the JD names terms the example Fact Bank lacks"
    text = _story_text(dict(out, jd_keywords=[SENTINEL]), monkeypatch)
    assert any(t.startswith("Role Keywords:") and SENTINEL in t for t in text)


def test_user_switch_per_run(monkeypatch, tmp_path, capsys):
    """`engine keywords on|off` is the start-of-run choice: live for every container, and the env var still wins."""
    monkeypatch.delenv("REGEN_JD_KEYWORDS", raising=False)
    monkeypatch.setattr(keywords, "PATH", str(tmp_path / "keywords.json"))
    assert not keywords.enabled()                      # nothing chosen yet: off
    keywords.main(["on"])
    assert keywords.enabled() and "ON" in capsys.readouterr().out
    assert tailor(_lane(), JD).get("jd_keywords")
    monkeypatch.setenv("REGEN_JD_KEYWORDS", "0")       # an explicit env choice beats the file
    assert not keywords.enabled()
    monkeypatch.delenv("REGEN_JD_KEYWORDS")
    keywords.main(["off"])
    assert not keywords.enabled() and "jd_keywords" not in tailor(_lane(), JD)
    (tmp_path / "keywords.json").write_text("{broken")  # a damaged file falls back to off, never on
    assert not keywords.enabled()
    with pytest.raises(SystemExit):
        keywords.main(["maybe"])


@pytest.mark.parametrize("flag", ["0", "1"])
def test_build_reads_only_vouched_keys(flag, monkeypatch):
    monkeypatch.setenv("REGEN_JD_KEYWORDS", flag)
    out = tailor(_lane(), JD)
    out.pop("_coverage", None)
    spy = _Spy(out)
    _story_text(spy, monkeypatch)
    unknown = {k for k in spy.read if not k.startswith("_")} - VALIDATED - COMPOSED - FLAGGED - PLUMBING
    assert not unknown, f"resume.build() prints spec keys nothing vouches for: {sorted(unknown)}"


def test_validate_checks_every_bank_backed_key():
    """Each key listed as VALIDATED is really rejected by validate() when it points outside the Fact Bank."""
    base = tailor(_lane(), JD)
    resume.validate(base)
    bad = {
        "roles": [["no_such_role", []]],
        "projects": ["no_such_project"],
        "skills": ["no_such_skill"],
        "skill_text": {base["skills"][0]: "Invented Skill, Another Invented Skill"},
        "fact_pick": {"no_such_fact": [0]},
    }
    assert set(bad) == VALIDATED
    for key, value in bad.items():
        with pytest.raises(SystemExit, match=re.escape("not in the Fact Bank")):
            resume.validate(dict(base, **{key: value}))
