"""Applier worker: claim batches from a shared inbox and apply them. One worker = one browser = one container.

    python -m engine worker [--once]

Scale-out without a broker: the shared workspace *is* the queue.
  workspace/batches/inbox/<name>.json    dropped by the pipeline (REGEN_APPLIERS=docker) or by hand
  workspace/batches/claimed/<name>.json  os.rename is atomic on one filesystem, so exactly one worker wins a batch
  workspace/batches/done/<name>.json     finished; the pipeline waits for every part to land here
Each worker logs to workspace/logs/<name>.log (same as local appliers), writes email-code requests to
workspace/codes/*.wait (the operator's watcher sees them no matter which container asked) and keeps its own browser
profile inside the container. `docker compose -f deploy/appliers.compose.yml up -d --scale applier=N` sets capacity.
Stop: create workspace/batches/STOP (every worker exits after its current batch).
"""
import os, socket, subprocess, sys, time

from engine.config import ROOT, WORKSPACE

BOX = os.path.join(WORKSPACE, "batches")
DIRS = {k: os.path.join(BOX, k) for k in ("inbox", "claimed", "done")}


def claim():
    """Oldest inbox batch this worker managed to rename into claimed/, or None. O(inbox)."""
    for d in DIRS.values():
        os.makedirs(d, exist_ok=True)
    def age(n):  # another worker may claim (rename) a file between listdir and stat
        try:
            return os.path.getmtime(os.path.join(DIRS["inbox"], n))
        except OSError:
            return float("inf")
    for name in sorted(os.listdir(DIRS["inbox"]), key=age):
        if not name.endswith(".json") or name.startswith("."):  # ".x.json" is still being written
            continue
        try:
            os.rename(os.path.join(DIRS["inbox"], name), os.path.join(DIRS["claimed"], name))
            return name
        except OSError:
            continue  # another worker won it
    return None


def apply_one(name):
    """Run `engine apply` on a claimed batch (a child process, like local appliers), then move it to done/."""
    log = open(os.path.join(WORKSPACE, "logs", name[:-5] + ".log"), "a", encoding="utf-8")
    log.write(f"worker {socket.gethostname()} claimed {name}\n")
    log.flush()
    rc = subprocess.call([sys.executable, "-m", "engine", "apply", f"batches/claimed/{name}"], cwd=ROOT,
                         env=dict(os.environ, PYTHONUNBUFFERED="1"), stdout=log, stderr=subprocess.STDOUT)
    os.replace(os.path.join(DIRS["claimed"], name), os.path.join(DIRS["done"], name))
    return rc


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    os.makedirs(os.path.join(WORKSPACE, "logs"), exist_ok=True)
    print(f"worker {socket.gethostname()}: watching {DIRS['inbox']}", flush=True)
    while not os.path.exists(os.path.join(BOX, "STOP")):
        name = claim()
        if name:
            print(f"apply {name} -> rc {apply_one(name)}", flush=True)
        elif "--once" in argv:
            return
        else:
            time.sleep(5)


if __name__ == "__main__":
    main()
