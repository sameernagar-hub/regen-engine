"""CLI: python -m engine <command> [args]

  scan    [days] [--ats a,b]       Greenhouse + Ashby + Lever boards -> workspace/queue.json
  newgrad [days]                   newgrad-jobs.com leads, resolved to the employer's ATS -> queue.json / leads.json
  watch   [min] [--once] [--newgrad] poll all boards continuously; announce only brand-new matches (REGEN_WEBHOOK)
  feed    [days]                   SimplifyJobs new-grad feed -> workspace/feed_queue.json
  boards  [harvest|recheck]        grow the board registry / retry boards marked dead (workspace/boards.json)
  batch  <name> <id,id,...>        queue ids -> tailored resumes + workspace/batches/<name>.json
  tailor <spec.json>               build one Fact-Bank-only resume
  apply  <batches/x.json> [--dry]  fill (and submit) every job in a batch
  inspect <job url> [--show]       list a form's fields + the engine's answers, without filling it
  status                           application outcomes from the event log
  inbox   <msgs.json> | --imap [d] classify recruiting email -> outcome events (OA / interview / rejection / offer / scam)
  learn                            response rates by lane and ATS -> workspace/learnings.md
  sos-test                         send a test SOS alert (engine/notify.py; .env SMTP app password)
  live    [port]                   the engine, watched live (localhost page; read-only)
  report  [YYYY-MM-DD]             verified submissions only: latest status SUBMITTED + a proof screenshot on disk
"""
import collections, sys


def status(_argv):
    from engine.feedback.events import read
    evs = read("application")
    latest = {}
    for e in evs:
        if not e.get("dry"):
            latest[e["job"]] = e
    by = collections.Counter(e["status"] for e in latest.values())
    print(f"{len(latest)} jobs tracked:", dict(by))
    for e in latest.values():
        print(f"  {e['status']:<10} {e['job'][:70]}")


def report(argv):
    """Count only what can be proven: each job's latest status is SUBMITTED and its proof screenshot exists."""
    import os
    from engine.config import WORKSPACE
    from engine.feedback.events import read
    day = argv[0] if argv else None
    latest = {}
    for e in read("application"):
        if not e.get("dry"):
            latest[e.get("url") or e["job"]] = e
    rows = [e for e in latest.values() if e["status"] == "SUBMITTED" and (not day or e["ts"].startswith(day))]
    verified = [e for e in rows if e.get("proof") and os.path.exists(os.path.join(WORKSPACE, e["proof"]))]
    backfilled = [e for e in rows if e.get("backfilled")]
    print(f"{len(verified)} verified submissions" + (f" on {day}" if day else "") +
          f" (proof on disk){'; ' + str(len(backfilled)) + ' backfilled from the tracker without a stored proof path' if backfilled else ''}")
    for e in sorted(verified, key=lambda e: e["ts"]):
        print(f"  {e['ts'][:16].replace('T', ' ')}  {e['job'][:60]:<60}  {e['proof']}")


def boards(argv):
    from engine.discovery import ats
    if argv and argv[0] == "harvest":
        for a, (b, n) in ats.harvest().items():
            print(f"{a:<11} {b} -> {n} boards")
    elif argv and argv[0] == "recheck":
        b = ats.load_boards()
        dead = [d.split(":", 1) for d in b.get("dead", [])]
        _, still = ats.fetch_all({a: [t for x, t in dead if x == a] for a in ats.ATS})
        b["dead"] = sorted(f"{a}:{t}" for a, t in still)
        ats.save_boards(b)
        print(f"{len(dead) - len(still)} of {len(dead)} dead boards are back")
    else:
        b = ats.load_boards()
        print({a: len(b[a]) for a in ats.ATS}, "dead:", len(b.get("dead", [])))


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); return
    cmd, argv = sys.argv[1], sys.argv[2:]
    if cmd == "scan":
        from engine.discovery.scan import main as m
    elif cmd == "watch":
        from engine.discovery.watch import main as m
    elif cmd == "newgrad":
        from engine.discovery.newgrad import main as m
    elif cmd == "boards":
        m = boards
    elif cmd == "feed":
        from engine.discovery.simplify import main as m
    elif cmd == "batch":
        from engine.tailoring.batch import main as m
    elif cmd == "tailor":
        from engine.tailoring.resume import main as m
    elif cmd == "apply":
        from engine.apply.runner import main as m
    elif cmd == "inspect":
        from engine.apply.inspect_form import main as m
    elif cmd == "status":
        m = status
    elif cmd == "report":
        m = report
    elif cmd == "live":
        from engine.live.server import main as m
    elif cmd == "inbox":
        from engine.feedback.inbox import main as m
    elif cmd == "learn":
        from engine.feedback.inbox import learn
        m = lambda _argv: learn()
    elif cmd == "sos-test":
        from engine.notify import sos
        m = lambda _argv: sos("[REGEN] test alert", "If you can read this, SOS alerts work.")
    else:
        raise SystemExit(f"unknown command {cmd!r}\n{__doc__}")
    m(argv)


if __name__ == "__main__":
    main()
