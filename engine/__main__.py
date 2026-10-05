"""CLI: python -m engine <command> [args]

  scan   [days]                    Greenhouse boards -> workspace/queue.json
  feed   [days]                    SimplifyJobs new-grad feed -> workspace/feed_queue.json
  batch  <name> <id,id,...>        queue ids -> tailored resumes + workspace/batches/<name>.json
  tailor <spec.json>               build one Fact-Bank-only resume
  apply  <batches/x.json> [--dry]  fill (and submit) every job in a batch
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


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); return
    cmd, argv = sys.argv[1], sys.argv[2:]
    if cmd == "scan":
        from engine.discovery.greenhouse import main as m
    elif cmd == "feed":
        from engine.discovery.simplify import main as m
    elif cmd == "batch":
        from engine.tailoring.batch import main as m
    elif cmd == "tailor":
        from engine.tailoring.resume import main as m
    elif cmd == "apply":
        from engine.apply.runner import main as m
    elif cmd == "status":
        m = status
    else:
        raise SystemExit(f"unknown command {cmd!r}\n{__doc__}")
    m(argv)


if __name__ == "__main__":
    main()
