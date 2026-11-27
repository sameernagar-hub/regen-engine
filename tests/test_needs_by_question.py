"""needs_by_question (MCP): full question text, the options a form showed, and the human-only filter (11-25)."""
from types import SimpleNamespace as NS

from engine.connectors import mcp_server as M

LONG = "How many years of professional experience do you have building distributed backend systems in production at scale?"
assert len(LONG) > 90


def fake_api(monkeypatch, items, events):
    api = NS(human=lambda: items, store=NS(read=lambda: list(enumerate(events))))
    monkeypatch.setattr(M, "_api", lambda: api)


def item(job, *missing, text="x"):
    return NS(job=job, missing=list(missing), text=text)


def test_full_question_options_and_default_filter(monkeypatch):
    fake_api(monkeypatch, [
        item("A - SWE", LONG), item("B - SWE", LONG),
        item("C - SWE", "Are you legally authorized to work in the US?"),
        item("D - SWE", text="NEEDS YOU: the form has a human-only field (bot check)"),
        item("E - SWE", "Please tick the hCaptcha box"),
    ], [{"kind": "application", "job": "A - SWE", "options": {LONG: ["0-1", "2-4", "5+"]}}])
    rows = M.needs_by_question()
    assert [r["question"] for r in rows] == [LONG]  # nothing cut at 90; CAPTCHA / human-click / user_only dropped
    assert rows[0]["count"] == 2 and rows[0]["options"] == ["0-1", "2-4", "5+"] and "user_only" in rows[0]


def test_filter_off_shows_everything_user_only_last(monkeypatch):
    fake_api(monkeypatch, [item("A - SWE", LONG), item("C - SWE", "Are you legally authorized to work in the US?"),
                           item("E - SWE", "Please tick the hCaptcha box")], [])
    rows = M.needs_by_question(skip_human_only=False)
    assert len(rows) == 3 and rows[-1]["user_only"] is True and "options" not in rows[0]


def test_runner_keeps_long_labels_and_notes_options():
    from engine.apply import runner
    assert runner.MAX_Q >= 300
    job = {}
    runner.note_options(job, LONG, [("0-1", None), ("2-4", None), ("", None)])
    assert job["_options"] == {LONG: ["0-1", "2-4"]}


def test_workday_keeps_long_labels_and_options():
    import inspect
    from engine.apply import workday
    src = inspect.getsource(workday)
    assert "label[:90]" not in src and "note_options(job, label, opts)" in src and "options=" in src


def test_refresh_picks_cut_questions_only(monkeypatch):
    from engine import shadow
    cut, full = "x" * 90, "How many years of professional experience do you have?"
    ev = [{"url": "u1", "job": "A - SWE", "detail": "NEEDS YOU: " + cut},
          {"url": "u2", "job": "B - SWE", "detail": "NEEDS YOU: " + full},
          {"url": "u3", "job": "C - SWE", "detail": "NEEDS YOU: " + cut + " | Please tick the hCaptcha box"},
          {"url": "u4", "job": "D - SWE", "detail": "NEEDS YOU: " + cut}]
    import engine.feedback.events as E, engine.pipeline as P
    monkeypatch.setattr(E, "read", lambda kind=None: ev)
    monkeypatch.setattr(P, "latest_status", lambda: {"u1": "NEEDS YOU", "u2": "NEEDS YOU", "u3": "NEEDS YOU", "u4": "SUBMITTED"})
    assert shadow.cut_jobs() == ["A - SWE"]
