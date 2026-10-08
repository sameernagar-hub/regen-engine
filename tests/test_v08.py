"""v0.8: round-robin scheduler, Fact Bank drafts, locked event log, long-term sponsorship rule, faster tailoring."""
import json, os, subprocess, sys, textwrap

import pytest

from engine.apply import drafts
from engine.apply.scheduler import Q_DEFAULT, Q_MAX, Q_MIN, Quantum, RoundRobin, Task, poll, wait
from engine.config import WORKSPACE
from engine.feedback import events


# ---------------- scheduler ----------------
class FakeClock:
    """Deterministic time: work advances it explicitly, sleep() jumps it."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def job(clock, trace, name, steps):
    """steps: list of ("work", seconds) / ("wait", seconds) / ("check",)"""
    def make(res):
        def g():
            for kind, *a in steps:
                trace.append((name, res, kind))
                if kind == "work":
                    clock.t += a[0]
                    yield
                elif kind == "wait":
                    yield a[0]
            return name
        return g()
    return make


def test_rr_overlaps_waits_and_respects_concurrency():
    c, trace = FakeClock(), []
    rr = RoundRobin(Quantum(), concurrency=2, clock=c, sleep=c.sleep)
    tasks = [Task(n, "gh", job(c, trace, n, [("work", 1), ("wait", 10), ("work", 1)])) for n in "abc"]
    done = rr.run(tasks, ["tab1", "tab2", "tab3"])
    assert sorted(t.result for t in done) == ["a", "b", "c"]
    # sequential would be 3 * 12 = 36 s; with 2 tabs a and b wait together, then c: 1+1 (+10 wait) ... = 24 s
    assert c.t == pytest.approx(24.0)
    assert {r for _, r, _ in trace} <= {"tab1", "tab2"}  # only `concurrency` tabs ever used


def test_rr_preempts_at_quantum():
    c, trace = FakeClock(), []
    q = Quantum()
    rr = RoundRobin(q, concurrency=2, clock=c, sleep=c.sleep)
    long = [("work", 2)] * 6            # 12 s of CPU in 2 s bursts, quantum is the 6 s default
    tasks = [Task("long", "x", job(c, trace, "long", long)), Task("short", "y", job(c, trace, "short", [("work", 1)]))]
    done = {t.name: t for t in rr.run(tasks, ["t1", "t2"])}
    order = [n for n, _, _ in trace]
    assert order.index("short") < len(order) - 1   # short ran before long finished: long was preempted
    assert done["long"].preempted >= 1
    assert done["long"].active == pytest.approx(12.0)


def test_rr_isolates_failures():
    c = FakeClock()

    def boom(res):
        def g():
            yield
            raise RuntimeError("page crashed")
        return g()
    rr = RoundRobin(Quantum(), concurrency=1, clock=c, sleep=c.sleep)
    done = rr.run([Task("bad", "x", boom), Task("good", "x", job(c, [], "good", [("work", 1)]))], ["t"])
    by = {t.name: t for t in done}
    assert isinstance(by["bad"].error, RuntimeError) and by["good"].result == "good"


def test_quantum_ewma_and_clamp(tmp_path):
    q = Quantum(str(tmp_path / "q.json"))
    assert q.get("ashby") == Q_DEFAULT          # no samples yet
    for b in (3, 3, 3, 3):
        q.update("ashby", b)
    assert q.get("ashby") == pytest.approx(3.0)  # zero variance -> the mean
    for b in (100, 100, 100):
        q.update("ashby", b)
    assert q.get("ashby") == Q_MAX              # clamped
    q.update("tiny", 0.01); q.update("tiny", 0.01); q.update("tiny", 0.01)
    assert q.get("tiny") == Q_MIN
    q.update("ignored", 0)                       # zero / negative bursts carry no information
    assert "ignored" not in q.stats
    q.save()
    assert Quantum(str(tmp_path / "q.json")).stats["ashby"][2] == 7  # persisted sample count


def test_quantum_survives_corrupt_file(tmp_path):
    p = tmp_path / "q.json"
    p.write_text("{not json")
    assert Quantum(str(p)).stats == {}


def test_wait_and_poll_helpers():
    assert list(wait(2)) == [2.0]
    seen = iter([None, None, "ok"])
    g = poll(lambda: next(seen), timeout=60, every=0.5)
    assert next(g) == 0.5 and next(g) == 0.5
    with pytest.raises(StopIteration) as stop:
        next(g)
    assert stop.value.value == "ok"
    g = poll(lambda: None, timeout=0)
    with pytest.raises(StopIteration) as stop:
        next(g)
    assert stop.value.value is None


# ---------------- drafts ----------------
FB = {"roles": {"acme": ["Acme Corp", "Software Engineer", "City, ST", "2023 - Present"],
                "beta": ["Beta Labs", "Engineer", "City, ST", "2021 - 2023"]},
      "facts": {"a_api": "Built <b>12 REST APIs</b> -- used by 3 teams.",
                "a_fix": "Debugged a silent production failure and added contract tests pinning the response shape.",
                "a_llm": "Built LLM agents with tool calling.",
                "b_etl": "Rebuilt the nightly ETL job."}}
JOB = {"name": "Initech - Backend Engineer", "resume": "out/Resume_Initech_1.pdf"}


def test_draft_only_open_questions():
    assert drafts.is_open("Why do you want to work at Initech?")
    assert drafts.is_open("Describe a time you kept pushing on something")
    for q in ("Will you require visa sponsorship?", "What is your desired salary?", "Gender", "LinkedIn profile",
              "What is your phone number?", "Are you authorized to work in the US?", "Do you agree to arbitration?", ""):
        assert not drafts.is_open(q), q
        assert drafts.draft(q, JOB, FB, WORKSPACE) is None


def test_draft_uses_only_fact_bank_text(tmp_path):
    os.makedirs(tmp_path / "specs")
    (tmp_path / "specs" / "Initech_1.json").write_text(json.dumps({"roles": [["acme", ["a_api", "a_llm"]], ["beta", ["b_etl"]]]}))
    text, fids = drafts.draft("Why are you interested in Initech?", JOB, FB, str(tmp_path))
    assert fids == ["a_api", "a_llm"]               # the resume spec's order (already ranked by JD overlap)
    assert "At Acme Corp, I built 12 REST APIs, used by 3 teams." in text
    assert "I also built LLM agents with tool calling." in text   # same employer -> no repeated "At Acme Corp"
    assert "Backend Engineer" in text and "Initech" in text and "<b>" not in text


def test_draft_persistence_story_needs_a_real_fix(tmp_path):
    text, fids = drafts.draft("Describe a time you kept pushing when most people would have stopped.", JOB, FB, str(tmp_path))
    assert fids == ["a_fix"]                        # no spec: falls back to the whole bank, picks the failure story
    assert "pinned down with tests" in text         # closing only because the fact itself mentions tests
    fb = {"roles": FB["roles"], "facts": {"a_api": FB["facts"]["a_api"]}}
    text, _ = drafts.draft("Tell us about a challenge you overcame", JOB, fb, str(tmp_path))
    assert "pinned down" not in text                # no failure fact -> no claim about fixing anything


def test_draft_kinds_and_review_log(tmp_path):
    assert drafts.kind_of("If you had one month to learn anything") == "learn"
    assert drafts.kind_of("How do you use AI tools today?") == "ai"
    assert drafts.kind_of("What's something you've built that you're proud of?") == "built"
    text, _ = drafts.draft("How do you use AI in your work?", JOB, FB, str(tmp_path), {"ai_tools": "I use Claude Code daily."})
    assert text.startswith("I use Claude Code daily.") and "LLM agents" in text
    assert drafts.draft("Why us?", JOB, {"roles": {}, "facts": {}}, str(tmp_path)) is None  # empty bank: nothing to say
    drafts.log_review(str(tmp_path), JOB, "Why us?", "answer", ["a_api"])
    log = (tmp_path / "drafts_review.md").read_text(encoding="utf-8")
    assert "Initech - Backend Engineer" in log and "_facts: a_api_" in log


# ---------------- event log ----------------
WRITER = textwrap.dedent("""
    import os, sys
    os.environ["REGEN_WORKSPACE"] = sys.argv[1]
    sys.path.insert(0, sys.argv[2])
    from engine.feedback.events import record
    for i in range(200):
        record("t", who=sys.argv[3], i=i, pad="x" * 3000)   # large lines are the ones that tore before
""")


def test_concurrent_writers_never_tear_lines(tmp_path):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = tmp_path / "w.py"
    script.write_text(WRITER)
    procs = [subprocess.Popen([sys.executable, str(script), str(tmp_path), root, w]) for w in "abc"]
    assert all(p.wait(60) == 0 for p in procs)
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 600
    assert all(json.loads(l)["kind"] == "t" for l in lines)   # every line parses: no interleaving


def test_read_is_incremental_and_tolerant(monkeypatch, tmp_path):
    monkeypatch.setattr(events, "WORKSPACE", str(tmp_path))
    events._cache.update(path=None)
    events.record("application", job="A")
    assert [e["job"] for e in events.read("application")] == ["A"]
    with open(tmp_path / "events.jsonl", "a", encoding="utf-8") as fh:
        fh.write('{"broken json\n')
    events.record("application", job="B")
    assert [e["job"] for e in events.read("application")] == ["A", "B"]
    assert events.bad_lines() == 1
    with open(tmp_path / "events.jsonl", "a", encoding="utf-8") as fh:
        fh.write('{"kind": "application", "job": "C"')  # a line still being written is not consumed yet
    assert len(events.read("application")) == 2
    with open(tmp_path / "events.jsonl", "a", encoding="utf-8") as fh:
        fh.write("}\n")
    assert [e["job"] for e in events.read("application")] == ["A", "B", "C"]
    (tmp_path / "events.jsonl").write_text("")  # truncated / replaced file: start over
    assert events.read() == []
    events._cache.update(path=None)


# ---------------- answers and airbags ----------------
def test_long_term_sponsorship_is_not_the_today_question():
    from engine.apply.runner import answer_for, P
    from engine import safety
    assert P["authorized_without_sponsorship_long_term"] == "No"   # derived: needs sponsorship in future -> No
    q = "Are you located in and able to work in the US without visa sponsorship for the next 5 years?"
    assert answer_for(q, {}) == "No"
    assert answer_for("Are you legally authorized to work in the US without sponsorship long-term?", {}) == "No"
    # the airbag agrees with "No" and would stop a "Yes"
    assert safety.check_answers([[q, "No"]], P) == []
    assert safety.check_answers([[q, "Yes"]], P)


def test_state_rule_regex_is_clean():
    """A heredoc once turned `\\b` into a backspace character inside a rule, so it never matched."""
    import engine.apply.runner as R
    src = open(R.__file__, encoding="utf-8").read()
    assert not any(ord(ch) < 9 or 13 < ord(ch) < 32 for ch in src)
    assert R.answer_for("What is your state of residence?", {}) == R.P["state"]


def test_drafts_stay_out_of_dropdowns(monkeypatch):
    from engine.apply import runner
    from engine.apply.runner import MAX_OPTION, set_gh, set_field
    monkeypatch.setattr(runner, "AUTOFILL", False)  # the plain guard; the autofill choice path is test_best_by_overlap_*

    class El:  # minimal stand-in for a form field holding a dropdown
        def __init__(self, sel):
            self.sel = sel

        def query_selector(self, q):
            return object() if self.sel and q.startswith(("input[role=combobox]", "select")) else None

        def query_selector_all(self, q):
            return []
    long = "x" * (MAX_OPTION + 1)
    def run(g):  # the helpers are generators now: drive them to their return value
        try:
            while True:
                next(g)
        except StopIteration as stop:
            return stop.value
    assert run(set_gh(None, El(True), long, "Which best describes your project?")) is False
    assert run(set_field(None, El(True), "Which best describes your project?", long)) is False


def test_preferred_office_picks_bay_area_then_remote():
    from engine.apply.runner import pick_option, P, answer_for
    P_loc = P.get("preferred_location")
    if not P_loc:
        pytest.skip("fixture has no preferred_location")
    assert pick_option([("Raleigh, NC", 1), ("San Mateo, CA", 2)], P_loc) == 2
    assert pick_option([("Raleigh, NC", 1), ("Remote (US)", 2)], P_loc) == 2
    assert answer_for("Which one of the following Initech office locations would you prefer?", {}) == P_loc


# ---------------- tailoring complexity work keeps behaviour ----------------
def test_distinct_respects_overlap_groups(monkeypatch):
    from engine.tailoring import resume, tailor
    monkeypatch.setattr(resume, "OVERLAPS", [["f1", "f2"], ["f3", "f4"]])
    assert tailor.distinct(["f1", "f2", "f3", "f5", "f4"], 3) == ["f1", "f3", "f5"]
    assert tailor.distinct(["f1", "f2"], 5) == ["f1"]


def test_vocabulary_is_cached_and_hits_match_word_boundaries():
    from engine.tailoring import tailor
    v1 = tailor.vocabulary()
    assert tailor.vocabulary() is v1                 # cached per loaded bank
    assert tailor._hits("we use Go and Rust", {"go", "rust"}) == {"go", "rust"}
    assert tailor._hits("good trust", {"go", "rust"}) == set()   # substring prefilter alone would say yes


def test_current_company_vs_previous_employer():
    from engine.apply.runner import answer_for, P
    assert answer_for("What company are you currently employed at or have worked at most recently?", {}) == P["current_employer"]
    assert answer_for("Have you ever been employed by Initech?", {}) == "No"


def test_experience_questions_only_yes_when_fact_bank_backs_it():
    from engine.apply.runner import experience_answer
    from engine.tailoring.tailor import vocabulary
    v = vocabulary()
    known = next(iter(sorted(t for t in v if t.isalpha() and len(t) > 3)))
    assert experience_answer(f"Do you have experience with {known}?") == "Yes"
    assert experience_answer("Do you have experience with COBOL mainframes?") is None   # never a guessed "No"
    assert experience_answer("What experience do you have?") is None


def test_select_all_skills_ticks_only_fact_bank_skills():
    from engine.apply.runner import answer_for, skill_options, pick_option
    from engine.tailoring.tailor import vocabulary
    q = "Which of the following have you used professionally in the last 3 years? Select all that apply."
    assert answer_for(q, {}) == "__SKILLS__"
    known = next(iter(sorted(t for t in vocabulary() if t.isalpha() and len(t) > 3)))
    assert skill_options([(known.title(), 1), ("COBOL", 2), ("Fortran 77", 3)]) == [1]
    assert pick_option([("Yes", 1)], "__SKILLS__") is None


def test_codes_only_go_to_the_named_company(tmp_path):
    from engine.apply import codes
    d = tmp_path / "codes"
    d.mkdir()
    (d / "initech_1.wait").write_text("Initech Labs - Software Engineer\nhttps://x")
    (d / "globex_2.wait").write_text("Globex - AI Engineer II\nhttps://y")
    (d / "acme_3.wait").write_text("Acme, Inc. - SWE\nhttps://z")
    (d / "done_4.wait").write_text("Done - SWE\nhttps://w")
    (d / "done_4.txt").write_text("ALREADY1")
    got = codes.match([{"company": "Initech Labs", "code": "Q1w2E3r4"}, {"company": "Globex", "code": "bad"},
                       {"company": "Acme", "code": "AbCd1234"}, {"company": "Done", "code": "ZZZZZZZZ"}], str(tmp_path))
    assert got == {"initech_1": "Q1w2E3r4", "acme_3": "AbCd1234"}   # malformed code ignored, answered job untouched
    assert (d / "done_4.txt").read_text() == "ALREADY1"
    assert [s for s, _ in codes.waiting(str(tmp_path))] == ["globex_2"]


def test_examples_of_ml_experience_is_a_built_question_not_learning():
    assert drafts.is_open("Please briefly provide examples of professional experience with Machine Learning")
    assert drafts.kind_of("Please briefly provide examples of professional experience with Machine Learning") == "built"
    assert drafts.kind_of("If you had one month to learn anything, what would it be?") == "learn"


def test_relatives_or_friends_and_background_check():
    from engine.apply.runner import answer_for, P
    assert answer_for("Do you have any relatives or friends currently working at the company?", {}) == P.get("relatives_at_company")


def test_stale_codes_are_never_used(tmp_path):
    import datetime as dt
    from engine.apply import codes
    d = tmp_path / "codes"
    d.mkdir()
    w = d / "globex_9.wait"
    w.write_text("Globex - SWE\nhttps://x")
    t = dt.datetime(2026, 10, 7, 22, 30)
    os.utime(w, (t.timestamp(), t.timestamp()))
    day = dt.date(2026, 10, 7)
    assert codes.fresh({"when": "22:31"}, t.timestamp(), day)
    assert codes.fresh({"when": "10:31 PM"}, t.timestamp(), day)
    assert not codes.fresh({"when": "22:17"}, t.timestamp(), day)      # sent before the job started waiting
    assert not codes.fresh({"when": "Oct 6"}, t.timestamp(), day)      # an older day
    assert codes.fresh({}, t.timestamp(), day)                          # no time given: caller vouched


def test_preferred_language_comes_from_the_fact_bank():
    from engine.apply.runner import answer_for, preferred_language
    from engine.tailoring.tailor import vocabulary
    lang = preferred_language()
    assert lang is None or lang.lower() in vocabulary()
    assert answer_for("What is your preferred coding language?", {}) == lang


def test_autofill_policy_never_overclaims_or_touches_status(monkeypatch):
    from engine.apply import runner as R
    monkeypatch.setattr(R, "_FB", FB)  # two-role fixture bank so rotation has something to rotate
    job = {"name": "Initech - Backend Engineer", "resume": "out/Resume_NoSpec_0.pdf"}  # no spec: draws from the whole fixture bank
    assert R.answer("Have you shipped a product used by 1 million users?", dict(job)) == "No"   # no fact backs it
    assert R.answer("Are you willing to work from our office 5 days a week?", dict(job)) == R.P.get("open_to_onsite_or_relocation", "Yes")
    assert R.answer("Do you have a portfolio that includes shipped consumer products?", dict(job)) in ("Yes", "No")
    for q in ("Please indicate whether you are a citizen or resident of any of the following countries: Cuba",
              "What is your desired salary?", "What is your gender?", "Have you ever been convicted of a felony?"):
        a = R.answer(q, dict(job))
        assert a is None or a == "__DECLINE__" or q.startswith("What is your desired salary"), (q, a)
    j = dict(job)
    a1, a2 = R.answer("Second example:", j), R.answer("Third example:", j)
    assert a1 and a2 and j["_drafted"][0][2] != j["_drafted"][1][2]   # rotation: different facts


def test_us_years_and_lived_in_us_question(monkeypatch):
    from engine.apply import runner as R
    fb = {"education": [["M.S. CS -- State University", "Aug 2024 - May 2026"], ["B.Tech -- Some University, India", "Aug 2018 - May 2022"]],
          "roles": {"x": ["Acme", "SWE", "City, ST", "Jan 2025 - Present"], "y": ["Foo", "SWE", "Pune, India", "Jan 2020 - Jan 2024"]}, "facts": {}}
    monkeypatch.setattr(R, "_FB", fb)
    y = R.us_years()
    assert 1.5 < y < 10
    want = "Yes" if y >= 1 else "No"
    assert R.derived("Have you lived in the United States for at least 1 of the past 5 years?") == want
    assert R.derived("Have you lived in the United States for at least 30 of the past 40 years?") == "No"


def test_best_by_overlap_picks_fact_backed_option():
    from engine.apply.runner import best_by_overlap
    from engine.tailoring.tailor import vocabulary
    known = next(iter(sorted(t for t in vocabulary() if t.isalpha() and len(t) > 3)))
    assert best_by_overlap([("Mobile games", 1), (f"Web apps with {known}", 2)], f"I built systems with {known}.") == 2
    assert best_by_overlap([("Mobile games", 1)], "nothing relevant") is None


def test_start_date_boxes_get_a_date_not_yes():
    import datetime, re as _re
    from engine.apply.runner import answer, answer_for, P
    a = answer("Ideal start date in office", {"name": "X - Y"})
    if _re.search(r"\d+ ?weeks?", P.get("start_date") or ""):
        assert _re.fullmatch(r"\d{2}/\d{2}/\d{4}", a) and datetime.datetime.strptime(a, "%m/%d/%Y").date() > datetime.date.today()
    assert answer_for("Start date month", {}) != P.get("start_date") or not P.get("start_date")   # education block untouched
