"""v0.15: Rippling moves from the reach list to the runner (FILLED), and the pipeline no longer parks its jobs."""
from engine.discovery import ats
from engine.apply import runner


def test_rippling_is_filled_not_reach():
    assert "rippling" in ats.APPLY_SUPPORTED and "rippling" in ats.FILLED
    assert "rippling" not in ats.REACH and "rippling" in ats.ATS
    assert "rippling" not in ats.SLUGGABLE  # board tokens are not guessable from a company name
    assert len(set(ats.ATS)) == len(ats.ATS)


def test_rippling_apply_url():
    u = "https://ats.rippling.com/acme-careers/jobs/0b1c"
    assert runner.rippling_apply_url(u) == u + "/apply?step=application"
    assert runner.rippling_apply_url(u + "/apply?x=1") == u + "/apply?step=application"
