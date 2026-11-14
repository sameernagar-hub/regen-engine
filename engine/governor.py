"""The governor: how many appliers the machine and the run can carry RIGHT NOW (the supervisor's judgement).

The gear is the range the user allows, supply (jobs waiting) is what is useful, the governor is what is safe. The
supervisor sizes the fleet to min(gear max, supply, governor ceiling) on every 15 s pass.

11-13: gear 3 grew the fleet to 7 appliers and the VM to 6.7 of 7.6 GB; page loads began to time out. The headroom
check in clone() only ran when an applier was CREATED, and a new applier is ~20 MB until its Chromium grows to
~700 MB, so every clone passed the check and nothing ever scaled the fleet back down. The governor re-judges every
pass from these signals:

  memory   VM MemAvailable vs a reserve, priced at the measured applier size (never below REGEN_APPLIER_MB)
  CPU      1-min load per CPU: above REGEN_MAX_LOAD hold, above REGEN_SHED_LOAD shed one
  health   share of recent applications (last 30 min) that died on page/browser timeouts: high -> shed one
  cap      today's verified submissions reached the daily cap -> down to the gear's minimum
  ramp     grow by one at a time, at most every GROW_COOLDOWN s (a new applier needs time to reach its real size);
           shed by one at most every SHED_COOLDOWN s (a drain lets the batch finish first)

Each pass writes workspace/fleet/governor.json (signals, ceiling, reasons) for the control room and MCP, and the
supervisor records a `supervisor` event only when the ceiling or its reasons change. Pure decide() for tests. O(1)
per pass plus the cached incremental events read.
"""
import datetime, json, os, re, time

from engine.config import WORKSPACE

STATE = os.path.join(WORKSPACE, "fleet", "governor.json")
MIN_FREE_MB = int(os.environ.get("REGEN_MIN_FREE_MB", "2048"))
APPLIER_MB = int(os.environ.get("REGEN_APPLIER_MB", "800"))
MAX_LOAD = float(os.environ.get("REGEN_MAX_LOAD", "0.7"))
SHED_LOAD = float(os.environ.get("REGEN_SHED_LOAD", "0.95"))
GROW_COOLDOWN = int(os.environ.get("REGEN_GROW_COOLDOWN", "120"))
SHED_COOLDOWN = int(os.environ.get("REGEN_SHED_COOLDOWN", "90"))
HEALTH_MIN, HEALTH_TIMEOUTS, HEALTH_RATE, HEALTH_WINDOW_MIN = 4, 2, 0.25, 30
TIMEOUT = re.compile(r"Timeout \d+ ?ms exceeded|Target (page|closed)|has been closed|crash|net::ERR_|Navigation failed"
                     r"|out of memory", re.I)


def machine(proc="/proc"):
    """{free_mb, load_per_cpu, cpus} from the VM's /proc, or {} when unreadable (not Linux)."""
    try:
        mem = {k: int(v.split()[0]) for k, v in (l.split(":", 1) for l in open(os.path.join(proc, "meminfo")))}
        load = float(open(os.path.join(proc, "loadavg")).read().split()[0])
    except (OSError, ValueError, IndexError):
        return {}
    cpus = os.cpu_count() or 1
    return {"free_mb": mem.get("MemAvailable", 0) // 1024, "load_per_cpu": round(load / cpus, 2), "cpus": cpus}


def applier_mb(containers):
    """Measured mean memory of running appliers (containers.json), never below APPLIER_MB."""
    ms = [c.get("mem_mb") or 0 for c in (containers or {}).get("containers") or []
          if c.get("service") == "applier" and c.get("state") == "running" and c.get("mem_mb")]
    return max(APPLIER_MB, round(sum(ms) / len(ms)) if ms else 0)


def health(events, now=None):
    """{recent, timeouts, rate} over application events of the last HEALTH_WINDOW_MIN minutes."""
    now = now or datetime.datetime.now()
    since = (now - datetime.timedelta(minutes=HEALTH_WINDOW_MIN)).isoformat()
    recent = [e for e in events if (e.get("ts") or "") >= since and not e.get("dry")]
    bad = sum(1 for e in recent if (e.get("status") or "") in ("FAILED", "ERROR") and TIMEOUT.search(e.get("detail") or ""))
    return {"recent": len(recent), "timeouts": bad, "rate": round(bad / len(recent), 2) if recent else 0.0}


def decide(lo, hi, running, m, per_mb, h, capped, last_grow=0.0, last_shed=0.0, now=None):
    """(ceiling, reasons). running = active appliers (not draining). Never above hi, never below lo."""
    now = now or time.time()
    ceiling, reasons, shed = hi, [], False
    if capped:
        ceiling = min(ceiling, lo)
        reasons.append("daily cap reached: down to the gear minimum")
    if m:
        free = m.get("free_mb", 0)
        if free < MIN_FREE_MB:
            shed = True
            reasons.append(f"memory low: {free} MB free < {MIN_FREE_MB} MB reserve")
        else:
            room = running + (free - MIN_FREE_MB) // max(1, per_mb)
            if room < ceiling:
                ceiling = room
                reasons.append(f"memory fits {room} appliers (~{per_mb} MB each, {free} MB free)")
        lpc = m.get("load_per_cpu", 0)
        if lpc > SHED_LOAD:
            shed = True
            reasons.append(f"CPU overloaded: load {lpc:.0%} per CPU")
        elif lpc > MAX_LOAD:
            ceiling = min(ceiling, running)
            reasons.append(f"CPU busy: load {lpc:.0%} per CPU, holding")
    if h.get("recent", 0) >= HEALTH_MIN and h.get("timeouts", 0) >= HEALTH_TIMEOUTS and h.get("rate", 0) >= HEALTH_RATE:
        shed = True
        reasons.append(f"timeouts: {h['timeouts']} of {h['recent']} recent applications")
    if shed:
        if now - last_shed >= SHED_COOLDOWN:
            ceiling = min(ceiling, running - 1)
        else:
            ceiling = min(ceiling, running)
            reasons.append("shed cooldown: holding")
    if ceiling > running:  # ramp: one at a time, after the last one had time to grow
        if now - last_grow >= GROW_COOLDOWN:
            ceiling = running + 1
        else:
            ceiling = running
            reasons.append("grow cooldown: holding")
    return max(lo, min(hi, ceiling)), reasons


def _state(workspace=None):
    return os.path.join(workspace, "fleet", "governor.json") if workspace else STATE


def _load(workspace=None):
    try:
        return json.load(open(_state(workspace), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(st, workspace=None):
    path = _state(workspace)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, path)


def _today_capped():
    """(submitted today, cap, reached)."""
    try:
        from engine import targeting
        from engine.feedback.events import read
        cap = targeting.cap()
        today = datetime.date.today().isoformat()
        n = sum(1 for e in read("application") if (e.get("status") or "").startswith("SUBMITTED") and not e.get("dry")
                and (e.get("ts") or "").startswith(today))
        return n, cap, n >= cap
    except Exception:
        return None, None, False


def same_reasons(why):
    """Reasons with their numbers masked: "memory fits 3 appliers (~800 MB each, 4217 MB free)" changes its free MB
    every pass, which wrote a govern event every ~15 s (11-13). An event is due only when the ceiling or the kind of
    reason changes."""
    return [re.sub(r"\d+", "#", r) for r in (why or [])]


def ceiling(lo, hi, running, wanted, workspace=None, proc="/proc"):
    """The supervisor's call: judge, persist the analytics snapshot, record a supervisor event on change.
    `wanted` = what supply alone asks for (for the snapshot only). Returns the ceiling. A workspace other than the
    live one (tests, bench scenarios) is isolated: only the ramp applies, no machine, ledger or cap signals."""
    from engine.feedback.events import read
    live = workspace in (None, WORKSPACE)
    st, now = _load(workspace), time.time()
    try:
        cont = json.load(open(os.path.join(workspace or WORKSPACE, "containers.json"), encoding="utf-8"))
    except (OSError, ValueError):
        cont = {}
    m, per = (machine(proc) if live else {}), applier_mb(cont)
    h = {"recent": 0, "timeouts": 0, "rate": 0.0}
    subs, cap, capped = None, None, False
    if live:
        try:
            h = health(read("application"))
        except Exception:
            pass
        subs, cap, capped = _today_capped()
    c, why = decide(lo, hi, running, m, per, h, capped, st.get("last_grow", 0), st.get("last_shed", 0), now)
    target = min(c, wanted)
    if target > running:
        st["last_grow"] = now
    elif target < running:
        st["last_shed"] = now
    snap = {**st, "ts": now, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "gear_range": [lo, hi], "running": running,
            "supply_wants": wanted, "ceiling": c, "target": target, "reasons": why, "machine": m, "applier_mb": per,
            "health": h, "submitted_today": subs, "daily_cap": cap}
    if live and (st.get("ceiling"), same_reasons(st.get("reasons"))) != (c, same_reasons(why)):
        try:
            from engine.feedback.events import record
            record("supervisor", action="govern", target=f"ceiling {c}", reasons=why, running=running,
                   free_mb=m.get("free_mb"), load=m.get("load_per_cpu"), timeouts=h.get("timeouts"))
        except Exception:
            pass
        print(f"supervisor: governor ceiling {c} (running {running}, supply {wanted}): {'; '.join(why) or 'clear'}",
              flush=True)
    _save(snap, workspace)
    return c


def main(argv=None):
    """`python -m engine governor`: print the last snapshot."""
    print(json.dumps(_load(), indent=1, default=str))


if __name__ == "__main__":
    main()
