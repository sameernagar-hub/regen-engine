"""The governor sizes the fleet from memory, CPU, timeouts and the daily cap, and ramps one applier at a time."""
import datetime

from engine import governor as g

NOW = 10_000.0
OK = {"free_mb": 6000, "load_per_cpu": 0.3, "cpus": 12}
CLEAR = {"recent": 0, "timeouts": 0, "rate": 0.0}


def test_grows_one_at_a_time():
    c, why = g.decide(1, 7, 2, OK, 800, CLEAR, False, last_grow=0, now=NOW)
    assert c == 3


def test_grow_cooldown_holds():
    c, why = g.decide(1, 7, 2, OK, 800, CLEAR, False, last_grow=NOW - 10, now=NOW)
    assert c == 2 and any("grow cooldown" in r for r in why)


def test_memory_room_caps_ceiling():
    # 2048 reserve, 3000 free -> room for 1 more at 800 MB
    m = {"free_mb": 3000, "load_per_cpu": 0.2}
    c, _ = g.decide(1, 7, 6, m, 800, CLEAR, False, last_grow=0, now=NOW)
    assert c == 7 or c == 6 + 1
    c, why = g.decide(1, 7, 6, {"free_mb": 2500, "load_per_cpu": 0.2}, 800, CLEAR, False, last_grow=0, now=NOW)
    assert c == 6 and any("memory fits" in r for r in why)


def test_low_memory_sheds_one():
    c, why = g.decide(1, 7, 7, {"free_mb": 900, "load_per_cpu": 0.5}, 700, CLEAR, False, now=NOW)
    assert c == 6 and any("memory low" in r for r in why)


def test_shed_cooldown_holds_instead_of_cascading():
    c, why = g.decide(1, 7, 6, {"free_mb": 900, "load_per_cpu": 0.5}, 700, CLEAR, False, last_shed=NOW - 20, now=NOW)
    assert c == 6 and any("shed cooldown" in r for r in why)


def test_cpu_hold_and_shed():
    c, _ = g.decide(1, 7, 3, {"free_mb": 6000, "load_per_cpu": 0.8}, 800, CLEAR, False, last_grow=0, now=NOW)
    assert c == 3
    c, _ = g.decide(1, 7, 3, {"free_mb": 6000, "load_per_cpu": 1.2}, 800, CLEAR, False, now=NOW)
    assert c == 2


def test_timeouts_shed():
    h = {"recent": 6, "timeouts": 3, "rate": 0.5}
    c, why = g.decide(1, 7, 4, OK, 800, h, False, now=NOW)
    assert c == 3 and any("timeouts" in r for r in why)


def test_daily_cap_goes_to_minimum():
    c, why = g.decide(1, 7, 4, OK, 800, CLEAR, True, now=NOW)
    assert c == 1 and any("daily cap" in r for r in why)


def test_never_below_gear_min_or_above_gear_max():
    c, _ = g.decide(1, 3, 1, {"free_mb": 100, "load_per_cpu": 2.0}, 800, CLEAR, False, now=NOW)
    assert c == 1
    c, _ = g.decide(1, 3, 3, OK, 800, CLEAR, False, last_grow=0, now=NOW)
    assert c == 3


def test_health_counts_only_recent_timeouts():
    now = datetime.datetime(2026, 11, 13, 14, 0)
    ev = [
        {"ts": "2026-11-13T13:50:00", "status": "FAILED", "detail": "FAILED: Page.goto: Timeout 30000ms exceeded."},
        {"ts": "2026-11-13T13:51:00", "status": "SUBMITTED", "detail": "SUBMITTED"},
        {"ts": "2026-11-13T13:52:00", "status": "FAILED", "detail": "FAILED: Select a country"},
        {"ts": "2026-11-13T12:00:00", "status": "FAILED", "detail": "Timeout 30000ms exceeded"},  # too old
    ]
    h = g.health(ev, now)
    assert h == {"recent": 3, "timeouts": 1, "rate": 0.33}


def test_applier_mb_uses_measured_size_with_floor():
    cont = {"containers": [{"service": "applier", "state": "running", "mem_mb": 1000},
                           {"service": "applier", "state": "running", "mem_mb": 1200},
                           {"service": "api", "state": "running", "mem_mb": 5000}]}
    assert g.applier_mb(cont) == 1100
    assert g.applier_mb({"containers": [{"service": "applier", "state": "running", "mem_mb": 20}]}) == g.APPLIER_MB


def test_reasons_compare_without_numbers():
    from engine.governor import same_reasons
    a = ["memory fits 3 appliers (~800 MB each, 4217 MB free)"]
    b = ["memory fits 3 appliers (~800 MB each, 4265 MB free)"]
    assert same_reasons(a) == same_reasons(b)
    assert same_reasons(a) != same_reasons(["grow cooldown: holding"])
