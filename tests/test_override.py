"""The human draft override (engine/override.py): what it answers, what it never answers, and that it re-opens jobs."""
import json

import pytest

from engine import override as O


P = {"us_citizen_or_us_person_itar": "No", "citizenship_country": "India", "address_line1": "1 Example St",
     "city": "Springfield", "state_abbr": "IL", "zip": "00000", "willing_background_check": "Yes",
     "work_auth_status": "Status X", "needs_sponsorship_now_or_future": "Yes"}


@pytest.fixture
def switch(tmp_path, monkeypatch):
    monkeypatch.setattr(O, "PATH", str(tmp_path / "override.json"))
    monkeypatch.setattr("engine.feedback.events.record", lambda *a, **k: None)
    return tmp_path


def test_off_by_default_and_toggles(switch):
    assert not O.on()
    O.set_state(True, "user said draft")
    assert O.on() and O.state()["note"] == "user said draft"
    O.set_state(False)
    assert not O.on()


def test_answers_from_presets_and_consent(switch):
    a = O.answer
    assert a("Please review and acknowledge the Candidate Arbitration Agreement", P) == "__ACK__"
    assert a("By clicking accept, you agree that any disputes related to your application...", P) == "__ACK__"
    assert a("Are you one of the following: U.S. Citizen or National. U.S. Lawful Permanent Resident.", P) == "No"
    assert a("Are you a national, citizen, or permanent resident of Belarus, Cuba, Iran, North Korea, Syria?", P) == "No"
    assert a("Does the deemed export rule affect your employment by Globex?", P) == "Yes"
    assert a("What are your preferred personal pronouns?", P) == "__DECLINE__"
    assert a("Current Legal Address", P) == "1 Example St, Springfield, IL, 00000"
    assert a("If yes, please confirm which type of Visa would be required", P) == "Status X; will need H-1B sponsorship in the future"
    assert a("As part of the hiring process, we ask all candidates to undergo a criminal background check. Are you willing?", P) == "Yes"


def test_never_invents_facts_or_passes_human_checks(switch):
    for q in ("Have you ever been convicted of a felony?", "We require all US-based employees to be fully vaccinated",
              "We're always curious - have you used Globex before?", "Do you currently have an active immigration case?",
              "Please include a copy of your college or university transcript."):
        assert O.blocked(q) == "fact" and O.answer(q, P) is None, q
    for q in ("To confirm you carefully read instructions, please select the SECOND option below",
              "We include this question to ensure each application is completed by a person."):
        assert O.blocked(q) == "human" and O.answer(q, P) is None, q


def test_override_reopens_parked_jobs(switch, monkeypatch):
    from engine import pipeline
    d = "NEEDS YOU: Please review and acknowledge the Candidate Arbitration Agreement"
    assert not pipeline.answerable_now(d)
    O.set_state(True)
    assert pipeline.answerable_now(d)
    assert not pipeline.answerable_now("NEEDS YOU: Have you ever been convicted of a felony?")
    rows = [{"kind": "application", "url": "https://x/1", "status": "NEEDS YOU", "detail": d, "ts": "2026-01-01T00:00:00"}] * 2
    monkeypatch.setattr(pipeline, "read", lambda kind=None: rows)
    assert pipeline.latest_status()["https://x/1"] == "RETRY"  # parked twice before the switch: tried again
