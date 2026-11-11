"""ALIVE Phase 0 (docs/ALIVE_PLAN.md §4-5): the typed event contract, its new emitters, and the scrubbed replay.

Covers every contract kind's mapping from a ledger event, the SSE split (narration vs signal), the supervisor's
problem lights (recorded only on change), Shadow's abstain record, and that a public replay holds no employer name,
URL, answer or waiting question, with the same submitted count as the live view (bench V7)."""
import json

import pytest

from engine.live import replay, server

U = "https://job-boards.greenhouse.io/initech/jobs/1"
TS = "2026-11-10T10:00:00"
LEDGER = [
    {"kind": "discovered", "job": "Initech - Backend Engineer", "url": U, "lag_min": 4},
    {"kind": "application", "job": "Globex - SRE", "url": "u2", "status": "SKIPPED", "detail": "JD: citizenship"},
    {"kind": "resume", "job": "Initech - Backend Engineer", "url": U, "lane": "backend", "ab_arm": "on", "facts": []},
    {"kind": "apply_start", "batch": "b1.json", "host": "h1", "jobs": [{"job": "Initech - Backend Engineer", "url": U}]},
    {"kind": "application", "job": "Initech - Backend Engineer", "url": U, "status": "SUBMITTED", "proof": "proof/none.png",
     "answers": [["Why us?", "Because of the Initech robotics team."]]},
    {"kind": "application", "job": "Umbrella - ML Engineer", "url": "u3", "status": "NEEDS YOU",
     "detail": "NEEDS YOU: Do you hold a license from the Umbrella board?"},
    {"kind": "application", "job": "Hooli - Data Engineer", "url": "u4", "status": "ERROR", "detail": "ERROR: timeout"},
    {"kind": "shadow", "action": "pickup", "by": "shadow", "job": "Umbrella - ML Engineer", "url": "u3", "conf": 0.8, "used": 2},
    {"kind": "shadow", "action": "abstain", "job": "Umbrella - ML Engineer", "url": "u3",
     "left": [{"q": "Are you authorized to work at Umbrella?", "why": "left for you"}]},
    {"kind": "shadow", "action": "configure", "mode": "calls"},
    {"kind": "shadow", "action": "call1", "job": "Umbrella - ML Engineer", "url": "u3"},
    {"kind": "outcome", "company": "Initech", "outcome": "oa", "jobs": ["Initech - Backend Engineer"]},
    {"kind": "gear", "gear": "2", "clutch": "on", "by": "operator"},
    {"kind": "keywords", "on": True, "by": "operator"},
    {"kind": "cap", "level": 2, "cap": 50},
    {"kind": "targeting", "key": "keywords_ab", "value": True},
    {"kind": "problem", "text": "pipeline is not running"},
    {"kind": "problem_clear", "text": "pipeline is not running"},
    {"kind": "outreach_sent", "company": "Initech", "role": ""},
    {"kind": "reach_mark", "mark": "submitted", "job": "Hooli - Data Engineer"},
    {"kind": "pipeline", "pass": 3},
    {"kind": "application", "job": "Dry - Run", "url": "u5", "status": "SUBMITTED", "dry": True},
]
LEDGER = [dict(e, ts=TS) for e in LEDGER]
NAMES = {"initech", "globex", "umbrella", "hooli"}


def test_every_contract_kind_maps_from_a_ledger_event():
    kinds = [server.kind_of(e) for e in LEDGER]
    assert set(server.STAGE_KINDS) <= set(kinds) and set(server.SIGNAL_KINDS) <= set(kinds)
    assert kinds[-2:] == ["internal", "internal"]  # pipeline plumbing and dry runs are never drawn
    assert server.kind_of({"kind": "brand_new_kind"}) == "unknown"  # bench V6 counts these and fails on any
    n = server.narrate(LEDGER[4])
    assert n["kind"] == "submitted" and n["job"] == U and n["company"] == "Initech" and "answers" not in n
    assert server.narrate(LEDGER[3])["jobs"] == [U]
    assert server.narrate(LEDGER[7])["conf"] == 0.8 and server.narrate(LEDGER[2])["detail"] == "arm on"
    assert server.narrate(LEDGER[12]) is None and server.signal(LEDGER[12])["detail"] == "2"


def test_stream_sends_signals_as_their_own_event_type():
    from apps.api import main as M
    frames = [f for i, e in enumerate(LEDGER) for f in M._sse(i + 1, e)]
    assert sum(f.startswith("event: narration") for f in frames) == 10
    sig = [json.loads(f.split("data: ", 1)[1]) for f in frames if f.startswith("event: signal")]
    assert [s["kind"] for s in sig] == ["shadow.mode", "gear", "keywords", "cap", "targeting", "problem",
                                       "problem.clear", "outreach.sent", "human.check"]


def test_problem_lights_record_only_on_change(monkeypatch):
    from engine import supervisor
    from engine.feedback import events
    got = []
    monkeypatch.setattr(events, "record", lambda kind, **kw: got.append((kind, kw.get("text"))))
    seen = set()
    assert supervisor.problems_changed(seen, ["no applier is alive"]) == (["no applier is alive"], [])
    assert supervisor.problems_changed(seen, ["no applier is alive"]) == ([], [])  # unchanged: nothing written
    supervisor.problems_changed(seen, [])
    assert got == [("problem", "no applier is alive"), ("problem_clear", "no applier is alive")]


def test_shadow_records_the_questions_it_leaves(monkeypatch):
    from engine import override, shadow
    from engine.feedback import answers as A, events
    got = []
    monkeypatch.setattr(events, "record", lambda kind, **kw: got.append((kind, kw)))
    monkeypatch.setattr(A, "save", lambda *a, **k: None)
    monkeypatch.setattr(shadow, "remember", lambda *a, **k: None)
    monkeypatch.setattr(override, "blocked", lambda q: "user" if "sponsor" in q else None)
    c = {"job": "Acme - SWE", "recommend": [{"q": "Will you need sponsorship?", "a": "No"}, {"q": "Pronouns?", "a": None},
                                            {"q": "Years of Python?", "a": "3", "conf": 0.9}]}
    left = shadow._use_recommendations(c, "u1")
    assert [w for _, w in left] == ["left for you", "nothing on file"] and shadow._conf(c) == 0.9
    assert got[0][0] == "shadow" and got[0][1]["action"] == "abstain" and got[0][1]["url"] == "u1"


def test_public_replay_is_scrubbed_and_matches_the_live_count():
    rows = replay.build("2026-11-10", LEDGER, NAMES)
    raw = json.dumps(rows).lower()
    assert not any(n in raw for n in NAMES)                       # V8: no employer names
    assert "http" not in raw and "because" not in raw              # no URLs, no answers
    assert "license" not in raw and "authorized" not in raw        # no question waiting on the candidate
    assert "pipeline is not running" not in raw                    # problem texts stay private
    live = sum(1 for e in LEDGER if (server.narrate(e) or {}).get("kind") == "submitted")
    assert sum(r["kind"] == "submitted" for r in rows) == live == 1  # V7: replay end state == live end state
    ids = [r["job"] for r in rows if r.get("job")]
    assert ids and all(len(i) == 10 for i in ids) and rows[0]["job"] == rows[2]["job"]  # same posting, same chip
    assert next(r for r in rows if r["kind"] == "gate.skip")["detail"] == "eligibility requirements"
    assert next(r for r in rows if r["kind"] == "cap")["detail"] == "2:50"


def test_replay_airbag_refuses_a_leak(monkeypatch):
    monkeypatch.setattr(replay, "masker", lambda names: (lambda t: t))
    monkeypatch.setattr(replay, "anonymize", lambda text, co: text)  # both scrubbers off: a name gets through
    with pytest.raises(SystemExit):
        replay.build("2026-11-10", LEDGER, NAMES)
