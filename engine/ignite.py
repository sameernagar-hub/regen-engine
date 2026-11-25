"""Ignition (11-24, user: "start the engine means start the agents ... an agent responsible to start the engine so I
can just call the agent and he knows what to do"). One call runs the whole start sequence after the stack is up:

    gear (default 3; 4 is refused, user 11-23)  ->  Role Keywords on|off  ->  daily cap level  ->  Shadow mode
    ->  every orchestrator agent resumed (hn, outreach, learn, report_rate, boards_recheck, shadow_retry, requeue)
    ->  a report: gearbox, cap, keywords, Shadow, orchestrator agents, fleet verdict, open cord asks

The Docker side (compose up, waiting for api + MCP) is scripts/ignite.sh, which calls this at the end. The same
function is the MCP tool `ignite`. The clean stop stays a separate, explicit step (gear N, cap 0, keywords off).

    python -m engine ignite [--gear 3] [--keywords on|off] [--cap 0-4] [--shadow autopilot|calls|off]
"""
import json, subprocess, sys

MAX_GEAR = "3"  # user 11-23: gear 4 strains memory; never above 3 from ignition


def _cli(*argv):
    r = subprocess.run([sys.executable, "-m", "engine", *argv], capture_output=True, text=True, timeout=120)
    return (r.stdout or r.stderr).strip().splitlines()[-1:] or [""]


def ignite(gear="3", keywords="on", cap=4, shadow="autopilot"):
    gear = str(gear).upper()
    if gear not in ("N", "1", "2", "3"):
        return {"error": f"gear {gear} refused: ignition runs at most gear {MAX_GEAR}"}
    if keywords not in ("on", "off"):
        return {"error": "keywords must be on or off"}
    if int(cap) not in range(5):
        return {"error": "cap level must be 0..4 (15/25/50/100/150 per day)"}
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
    return out


def main(argv):
    opts = {"gear": "3", "keywords": "on", "cap": 4, "shadow": "autopilot"}
    it = iter(argv)
    for a in it:
        if a.startswith("--") and a[2:] in opts:
            opts[a[2:]] = next(it, opts[a[2:]])
        else:
            raise SystemExit(__doc__)
    print(json.dumps(ignite(**opts), indent=1))
