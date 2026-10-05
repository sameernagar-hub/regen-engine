"""CLI: python -m engine <command> [args]

  scan    [days] [--ats a,b]       Greenhouse + Ashby + Lever boards -> workspace/queue.json
  newgrad [days]                   newgrad-jobs.com leads, resolved to the employer's ATS -> queue.json / leads.json
  watch   [minutes] [--once]       poll all boards continuously; announce only brand-new matches (REGEN_WEBHOOK)
  feed    [days]                   SimplifyJobs new-grad feed -> workspace/feed_queue.json
  boards  [harvest|recheck]        grow the board registry / retry boards marked dead (workspace/boards.json)
  batch  <name> <id,id,...>        queue ids -> tailored resumes + workspace/batches/<name>.json
  tailor <spec.json>               build one Fact-Bank-only resume
  apply  <batches/x.json> [--dry]  fill (and submit) every job in a batch
  inspect <job url> [--show]       list a form's fields + the engine's answers, without filling it
  status                           application outcomes from the event log
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
    else:
        raise SystemExit(f"unknown command {cmd!r}\n{__doc__}")
    m(argv)


if __name__ == "__main__":
    main()
