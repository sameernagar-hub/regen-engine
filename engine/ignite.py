"""Ignition (11-24, user: "start the engine means start the agents ... an agent responsible to start the engine so I
can just call the agent and he knows what to do"). One call runs the whole start sequence after the stack is up:

    gear (default 3; 4 is refused, user 11-23)  ->  Role Keywords on|off  ->  daily cap level  ->  Shadow mode
    ->  every orchestrator agent resumed (hn, outreach, learn, report_rate, boards_recheck, shadow_retry, requeue)
    ->  a report: gearbox, cap, keywords, Shadow, orchestrator agents, fleet verdict, open cord asks

The Docker side (compose up, waiting for api + MCP) is scripts/ignite.sh, which calls this at the end. The same
function is the MCP tool `ignite`. The clean stop stays a separate, explicit step (gear N, cap 0, keywords off).

    python -m engine ignite [--gear 3] [--keywords on|off] [--cap 0-4] [--shadow autopilot|calls|off]

The control room's key (/cord, POST /api/control/ignite) cannot write engine state from the API container: request()
drops workspace/ignite/request.json and the supervisor's next tick (apply_request) runs `engine ignite` with it as the
engine user. Every ignition, from any door, leaves its result in workspace/ignite/last.json; status() reads the live
switches (gear, keywords, cap, Shadow, paused agents) plus that last result.
"""
import json, os, subprocess, sys, time

from engine.config import WORKSPACE

DIR = os.path.join(WORKSPACE, "ignite")
REQUEST = os.path.join(DIR, "request.json")
LAST = os.path.join(DIR, "last.json")
_CHILD = None  # the supervisor's running ignition (Popen), reaped on the next tick

MAX_GEAR = "3"  # user 11-23: gear 4 strains memory; never above 3 from ignition


def _cli(*argv):
    r = subprocess.run([sys.executable, "-m", "engine", *argv], capture_output=True, text=True, timeout=120)
    return (r.stdout or r.stderr).strip().splitlines()[-1:] or [""]


def _check(gear, keywords, cap, shadow):
    """The one validation every door shares. Returns an error string or None."""
    if str(gear).upper() not in ("N", "1", "2", "3"):
        return f"gear {gear} refused: ignition runs at most gear {MAX_GEAR}"
    if keywords not in ("on", "off"):
        return "keywords must be on or off"
    try:
        if int(cap) not in range(5):
            raise ValueError
    except (TypeError, ValueError):
        return "cap level must be 0..4 (15/25/50/100/150 per day)"
    if shadow not in ("autopilot", "calls", "always", "off"):
        return "shadow must be autopilot, calls, always or off"
    return None


def ignite(gear="3", keywords="on", cap=4, shadow="autopilot", by="cli"):
    gear = str(gear).upper()
    err = _check(gear, keywords, cap, shadow)
    if err:
        return {"error": err}
    out = {}
    from engine import gearbox, orchestrator, shadow as S, cord
    out["gear"] = gearbox.shift(gear, "off", by="ignite").get("label")
    out["keywords"] = _cli("keywords", keywords)[0]
    out["cap"] = _cli("cap", str(int(cap)))[0]
    out["shadow"] = S.configure(mode=shadow, note="ignite").get("mode")
    out["agents"] = []
    for name in orchestrator.REGISTRY:
        orchestrator.command("resume", name, by="ignite")
        out["agents"].append(name)
    out["cord_open"] = len(cord.open_asks())
    try:
        from engine.feedback.events import record
        record("ignite", gear=gear, keywords=keywords, cap=int(cap), shadow=shadow)
    except Exception:
        pass
    try:
        _write(LAST, {"t": time.time(), "by": by, "asked": {"gear": gear, "keywords": keywords, "cap": int(cap),
                                                            "shadow": shadow}, "result": out})
    except OSError:
        pass
    return out


def _write(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(row, f)
    os.replace(tmp, path)


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def request(gear="3", keywords="on", cap=4, shadow="autopilot", by="control room", path=None):
    """Drop an ignition request for the supervisor (the API container never writes engine state). Latest wins."""
    gear = str(gear).upper()
    err = _check(gear, keywords, cap, shadow)
    if err:
        raise ValueError(err)
    _write(path or REQUEST, {"gear": gear, "keywords": keywords, "cap": int(cap), "shadow": shadow, "by": by,
                             "t": time.time()})
    return {"request": "ignite", "note": "the supervisor turns the key within 15 s"}


def apply_request(path=None, preexec=None):
    """Supervisor tick: run a pending request as `engine ignite ...` in a child (as the engine user via preexec),
    without blocking the tick. Returns True when one was started."""
    global _CHILD
    if _CHILD is not None and _CHILD.poll() is None:
        return False
    _CHILD = None
    path = path or REQUEST
    r = _load(path)
    if r is None:
        return False
    try:
        os.remove(path)
    except OSError:
        return False
    if _check(r.get("gear"), r.get("keywords"), r.get("cap"), r.get("shadow")):
        return False
    argv = [sys.executable, "-m", "engine", "ignite", "--gear", str(r["gear"]), "--keywords", r["keywords"],
            "--cap", str(int(r["cap"])), "--shadow", r["shadow"], "--by", str(r.get("by") or "control room")[:40]]
    _CHILD = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              preexec_fn=preexec if os.name != "nt" else None)
    return True


def status(last_path=None, request_path=None):
    """Live ignition switches + the last ignition. Every part is optional: a missing module reads as None."""
    out = {"gear": None, "gear_label": None, "keywords": None, "cap_level": None, "cap": None, "cap_levels": None,
           "shadow": None, "agents": {}}
    try:
        from engine import gearbox
        g = gearbox.spec()
        out.update(gear=g.get("gear"), gear_label=g.get("label"))
    except Exception:
        pass
    try:
        from engine.tailoring import keywords as K
        out["keywords"] = bool(K.enabled())
    except Exception:
        pass
    try:
        from engine import targeting as T
        t = T.status()
        out.update(cap_level=t.get("cap_level"), cap=t.get("cap"), cap_levels=t.get("cap_levels"))
    except Exception:
        pass
    try:
        from engine import shadow as S
        out["shadow"] = S.status().get("mode")
    except Exception:
        pass
    try:
        from engine import orchestrator
        out["agents"] = {k: bool(a.get("paused")) for k, a in orchestrator.status().get("agents", {}).items()}
    except Exception:
        pass
    out["last"] = _load(last_path or LAST)
    out["pending"] = os.path.exists(request_path or REQUEST)
    return out


def main(argv):
    opts = {"gear": "3", "keywords": "on", "cap": 4, "shadow": "autopilot", "by": "cli"}
    it = iter(argv)
    for a in it:
        if a.startswith("--") and a[2:] in opts:
            opts[a[2:]] = next(it, opts[a[2:]])
        else:
            raise SystemExit(__doc__)
    print(json.dumps(ignite(**opts), indent=1))
