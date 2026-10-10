"""Run control for the web UI: start one engine run with chosen filters, watch it, stop it.

    python -m engine.control '<json params>'      (what POST /api/control/run spawns)

A run is a list of steps (scan, newgrad, feed, apply), each an ordinary `python -m engine ...` command, executed in
order. Progress goes to workspace/run_ui.json (step, pid, started, finished, exit codes) so the UI can show which
stage is processing, and every step's output goes to workspace/logs/ui_<stamp>.log. Only one UI run at a time.
Nothing here decides anything new: the steps are the same CLI commands an operator would type.
"""
import datetime, json, os, signal, subprocess, sys, time

from engine.config import ROOT, WORKSPACE

STATE = os.path.join(WORKSPACE, "run_ui.json")
ATS_ALL = ("greenhouse", "lever", "ashby", "workable")


def defaults():
    return {"days": 3, "max": 60, "appliers": 3, "tabs": 3, "scan": True, "newgrad": True, "feed": True,
            "ats": ["greenhouse", "lever", "ashby"], "cap": 60, "dry": False, "loop": 0}


def clean(p):
    """Bound every knob (the UI is local, but a typo shouldn't launch 500 browsers)."""
    d = defaults()
    d.update({k: v for k, v in (p or {}).items() if k in d})
    d["days"] = max(1, min(int(d["days"]), 14))
    d["max"] = max(1, min(int(d["max"]), 200))
    d["appliers"] = max(1, min(int(d["appliers"]), 4))
    d["tabs"] = max(1, min(int(d["tabs"]), 5))
    d["cap"] = max(1, min(int(d["cap"]), 100))
    d["loop"] = max(0, min(int(d["loop"]), 240))  # minutes between first-applicant rescans (0 = one pass)
    d["ats"] = [a for a in d["ats"] if a in ATS_ALL] or ["greenhouse"]
    for k in ("scan", "newgrad", "feed", "dry"):
        d[k] = bool(d[k])
    return d


def steps(p):
    py = [sys.executable, "-m", "engine"]
    out = []
    if p["scan"]:
        out.append(("discover", py + ["scan", str(p["days"]), "--ats", ",".join(a for a in p["ats"] if a != "workable") or "greenhouse"]))
    if p["newgrad"]:
        out.append(("newgrad", py + ["newgrad", str(min(p["days"], 7))]))
    if p["feed"]:
        out.append(("feed", py + ["feed", str(min(p["days"], 7)), "--queue"]))
    out.append(("apply", py + ["run", "--no-scan", "--max", str(p["max"]), "--appliers", str(p["appliers"]), "--tabs", str(p["tabs"])]
                + (["--dry"] if p["dry"] else []) + (["--loop", str(p["loop"])] if p["loop"] else [])))
    return out


def read_state():
    try:
        s = json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"running": False}
    s["running"] = bool(s.get("pid")) and alive(s["pid"]) and not s.get("finished")
    return s


def alive(pid):
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def write(s):
    tmp = STATE + ".tmp"
    json.dump(s, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, STATE)


def start(params):
    """Spawn the runner detached; returns its state. Refuses while another UI run is alive."""
    cur = read_state()
    if cur.get("running"):
        raise RuntimeError("a run is already going")
    p = clean(params)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log = os.path.join(WORKSPACE, "logs", f"ui_{stamp}.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen([sys.executable, "-m", "engine.control", json.dumps(p), stamp], cwd=ROOT,
                            stdout=open(log, "w", encoding="utf-8"), stderr=subprocess.STDOUT,
                            creationflags=flags, start_new_session=os.name != "nt")
    s = {"pid": proc.pid, "params": p, "stamp": stamp, "log": os.path.relpath(log, WORKSPACE), "started": time.time(),
         "steps": [{"name": n, "status": "waiting"} for n, _ in steps(p)], "finished": None}
    write(s)
    s["running"] = True
    return s


def stop():
    s = read_state()
    if not s.get("pid"):
        return s
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(s["pid"])], capture_output=True)
    else:
        try:
            os.killpg(s["pid"], signal.SIGTERM)
        except OSError:
            pass
    s["finished"] = time.time()
    s["stopped"] = True
    write(s)
    s["running"] = False
    return s


def main(argv):
    p, stamp = clean(json.loads(argv[0])), argv[1]
    s = read_state()
    env = dict(os.environ, REGEN_MAX_PER_DAY=str(p["cap"]), PYTHONUNBUFFERED="1",
               REGEN_SKIP_ATS=",".join(a for a in ATS_ALL if a not in p["ats"]))
    for i, (name, cmd) in enumerate(steps(p)):
        s["steps"][i].update(status="running", started=time.time())
        write(s)
        print(f"== {name}: {' '.join(cmd[2:])}", flush=True)
        rc = subprocess.run(cmd, cwd=ROOT, env=env).returncode
        s["steps"][i].update(status="done" if rc == 0 else f"exit {rc}", finished=time.time())
        write(s)
    s["finished"] = time.time()
    write(s)


if __name__ == "__main__":
    main(sys.argv[1:])
