"""The desk queue (11-25): parked CAPTCHA jobs are pre-filled in the desk; the user solves the check and submits."""
from engine.apply import workday as W


def test_prefill_ats_routes_only_supported_boards():
    assert W.prefill_ats("https://boards.greenhouse.io/acme/jobs/1")
    assert W.prefill_ats("https://jobs.lever.co/acme/abc")
    assert W.prefill_ats("https://jobs.ashbyhq.com/acme/abc")
    assert W.prefill_ats("https://apply.workable.com/acme/j/ABC/")
    assert not W.prefill_ats("https://acme.wd5.myworkdayjobs.com/x")
    assert not W.prefill_ats("https://www.ycombinator.com/companies/acme/jobs/1")


def test_drive_runs_generator_and_returns_missing(monkeypatch):
    waits = []
    monkeypatch.setattr(W.time, "sleep", lambda s: waits.append(s))

    def gen():
        yield
        yield 2
        yield 99  # capped at 30 s
        return ["Cover letter"]
    assert W.drive(gen()) == ["Cover letter"]
    assert waits == [2.0, 30.0]


def test_prefill_never_submits(monkeypatch):
    from engine.apply import runner as R
    called = {}

    def fake_fill(page, job, log):
        called["fill"] = job["url"]
        yield 0
        return []
    monkeypatch.setattr(R, "fill_lever", fake_fill)
    monkeypatch.setattr(R, "submit_lever", lambda page: (_ for _ in ()).throw(AssertionError("submitted")))
    st = W.prefill(None, {"url": "https://jobs.lever.co/acme/abc", "resume": None}, print)
    assert called["fill"].endswith("/abc")
    assert st.startswith("NEEDS YOU: filled in the desk")
