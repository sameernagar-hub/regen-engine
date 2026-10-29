"""v1.2: the oil change (engine/oilchange.py), employer application caps, and the 10-27 rejection wordings."""
import datetime, json, os, time

from engine.config import WORKSPACE
from engine.feedback import inbox
from engine.feedback.events import record
from engine import oilchange as O, pipeline


def test_rejection_wordings_10_27():
    assert inbox.classify("Acme - an update on your application",
                          "We are sorry to inform you that you have not been selected for an interview on this occasion.") == "rejection"
    assert inbox.classify("Update On Your Application",
                          "Because we received more than five applications from you, this application was automatically closed") == "rejection"
    assert inbox.classify("Update on your interview with Acme",
                          "After careful consideration, we have elected to move forward in the interview process with "
                          "candidates whose experience and qualifications most closely align with the requirements.") == "rejection"
    # a confirmation that only mentions the possibility stays a confirmation
    assert inbox.classify("Thank you for applying to Acme", "If you are not selected, we will keep your resume on file.") == "confirmation"


def test_application_limit():
    assert inbox.application_limit("we limit candidates to a maximum of five applications within any 30-day period") == (5, 30)
    assert inbox.application_limit("no more than 3 applications in a 90 day window") == (3, 90)
    assert inbox.application_limit("thanks for applying") is None


def test_capped_companies():
    now = datetime.datetime.now()
    record("company_limit", company="Capco", max=2, days=30)
    for _ in range(2):
        record("application", job="Capco - Engineer", status="SUBMITTED", url="https://x/1")
    record("application", job="Freeco - Engineer", status="SUBMITTED", url="https://x/2")
    got = pipeline.capped(now + datetime.timedelta(seconds=5))
    assert "capco" in {c.lower() for c in got} and not any("freeco" in c.lower() for c in got)
    # outside the window the cap no longer applies
    assert not pipeline.capped(now + datetime.timedelta(days=31))


def test_posted_dates():
    today = datetime.date(2026, 10, 27)
    assert O._posted("10-20", today) == datetime.date(2026, 10, 20)
    assert O._posted("12-30", today) == datetime.date(2025, 12, 30)  # a future month-day is last year
    assert O._posted("2026-08-01T10:00", today) == datetime.date(2026, 8, 1)
    assert O._posted("", today) is None and O._posted("garbage", today) is None


def test_stale_queue():
    today = datetime.date(2026, 10, 27)
    q = [{"url": "https://a/1", "posted": "10-25"}, {"url": "https://a/2", "posted": "08-01"}, {"url": "https://a/3"}]
    stale = O.stale_queue(q, today)
    assert [j["url"] for j in stale] == ["https://a/2"]


def test_oil_life():
    now = time.time()
    fresh = {"last_change": now, "contaminants": {"workspace_mb": 40, "old_mail": 0, "build_cache_gb": 0.6, "stale_queue": 3}}
    life, wear = O.life(fresh, now)
    assert life == 90.0 and wear["workspace_mb"] == 10.0 and wear["build_cache_gb"] == 10.0
    dirty = dict(fresh, contaminants={**fresh["contaminants"], "build_cache_gb": 9})
    assert O.life(dirty, now)[0] == 0.0  # one contaminant over its limit empties the oil
    old = dict(fresh, last_change=now - O.INTERVAL_H * 1800)
    assert O.life(old, now)[0] == 50.0  # half the service interval gone
    assert O.life({"contaminants": {}}, now)[0] == 0.0  # never changed: due
    assert O.life(dict(fresh, contaminants={"bloated": [{"name": "a", "mem_mb": 2000}]}), now)[0] == 0.0


def test_dry_change_touches_nothing():
    os.makedirs(os.path.join(WORKSPACE, "logs"), exist_ok=True)
    old = os.path.join(WORKSPACE, "logs", "old.log")
    open(old, "w").write("x" * 1000)
    os.utime(old, (time.time() - 40 * 86400,) * 2)
    q = [{"url": "https://b/1", "posted": "01-02"}, {"url": "https://b/2", "posted": datetime.date.today().strftime("%m-%d")}]
    json.dump(q, open(os.path.join(WORKSPACE, "queue.json"), "w"))
    run = O.change(dry=True, by="test")
    names = [s["name"] for s in run["stages"]]
    assert names == list(O.STAGES)
    assert os.path.exists(old) and len(json.load(open(os.path.join(WORKSPACE, "queue.json")))) == 2
    drain = run["stages"][0]
    assert drain["removed"] >= 1
    assert run["stages"][3]["removed"] == 1  # the January posting would leave the queue
    st = O.load()
    assert not st.get("running") and not st.get("history")  # a dry run is not a service


def test_real_change_and_request():
    old = os.path.join(WORKSPACE, "logs", "older.log")
    open(old, "w").write("y" * 100)
    os.utime(old, (time.time() - 40 * 86400,) * 2)
    O.request("test")
    st = O.inspect(O.load(), slow=False)
    assert O.due(st)
    run = O.change(by="test")
    assert not os.path.exists(old) and not os.path.exists(O.REQUEST)
    st = O.load()
    assert st["history"][0]["started"] == run["started"] and st["last_change"]
    assert len(json.load(open(os.path.join(WORKSPACE, "queue.json")))) == 1
    assert st["life"] > 0 and not O.due(st)


def test_failed_change_backs_off():
    # 10-28: a change that could not lift oil life re-ran every 5 minutes; now the schedule waits an interval
    now = time.time()
    stuck = {"life": 0.0, "history": [{"started": now - 60, "finished": now - 50,
                                       "stages": [{"name": "check", "life_before": 0.0, "life_after": 0.0}]}]}
    if os.path.exists(O.REQUEST):
        os.remove(O.REQUEST)
    assert not O.due(stuck, now)
    assert O.due({**stuck, "history": []}, now)  # never changed: due
    assert O.due(stuck, now + O.INTERVAL_H * 3600 + 1)  # an interval later: try again
    O.request("test")
    assert O.due(stuck, now)  # asking always works
    os.remove(O.REQUEST)
