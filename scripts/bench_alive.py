"""ALIVE benchmarks, server side (docs/ALIVE_PLAN.md §6; added in Phase 0).

    python scripts/bench_alive.py [--events path/to/events.jsonl] [--save]

  V6  event coverage: every ledger kind maps to a contract kind or "internal" (0 unknown)
  V7  replay fidelity: the scrubbed replay's submitted count == the live view's, per day
  V8  public privacy: 0 employer names / URLs / emails in the day's replay
  S1  spine fidelity (Phase 0 acceptance): the page's fold (apps/web/lib/spine.ts, run by node) over the whole
      ledger ends with the same distinct submitted count as the ledger itself

--save appends one row to docs/bench/alive.md (date, commit, numbers). Browser numbers (V1-V5, V9, V10) are taken
in the preview from Phase 1 on. Read-only on the ledger. O(E).
"""
import collections, json, os, re, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def run(path=None):
    from engine.live import replay, server
    from engine.live.export import company_names
    if path:
        events = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    else:
        from engine.feedback.events import read
        events = read()
    kinds = collections.Counter(server.kind_of(e) for e in events)
    unknown = sorted({e.get("kind") for e in events if server.kind_of(e) == "unknown"})
    names = company_names(path)
    days = sorted({(e.get("ts") or "")[:10] for e in events if e.get("ts")})[-7:]
    v7, v8 = [], 0
    for d in days:
        rows = replay.build(d, events, names)  # raises (airbag) on any employer name
        day = [e for e in events if (e.get("ts") or "").startswith(d)]
        live = sum(1 for e in day if (server.narrate(e) or {}).get("kind") == "submitted")
        v7.append((d, live, sum(r["kind"] == "submitted" for r in rows)))
        raw = json.dumps(rows)
        v8 += len(re.findall(r"https?://|\S+@\S+\.\w+", raw))
    # S1: the page's own fold over the whole ledger, in node
    typed = []
    for i, e in enumerate(events):
        n = server.narrate(e)
        if n:
            typed.append({"type": "narration", "data": {"id": i + 1, "ts": e.get("ts"), **n}})
        else:
            g = server.signal(e)
            if g:
                typed.append({"type": "signal", "data": {"id": i + 1, "ts": e.get("ts"), **g}})
    ledger_submitted = len({e.get("url") or e.get("job") for e in events if e.get("kind") == "application"
                            and e.get("status") == "SUBMITTED" and not e.get("dry")})
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(typed, f)
    try:
        out = subprocess.run(["node", "scripts/spine_check.mjs", f.name], cwd=os.path.join(ROOT, "apps", "web"),
                             capture_output=True, text=True, timeout=300)
        spine = json.loads(out.stdout) if out.returncode == 0 else {"error": out.stderr[-300:]}
    except (OSError, subprocess.TimeoutExpired, ValueError) as ex:
        spine = {"error": str(ex)[:300]}
    finally:
        os.unlink(f.name)
    return {"events": len(events), "kinds": dict(kinds.most_common()), "V6_unknown": unknown,
            "V7": v7, "V7_ok": all(a == b for _, a, b in v7), "V8_hits": v8,
            "S1": {"ledger_submitted": ledger_submitted, "spine": spine,
                   "ok": spine.get("submitted") == ledger_submitted}}


def main(argv):
    path = argv[argv.index("--events") + 1] if "--events" in argv else None
    r = run(path)
    print(f"events {r['events']}")
    print(f"V6 event coverage: {'PASS' if not r['V6_unknown'] else 'FAIL'} (unknown kinds: {r['V6_unknown'] or 'none'})")
    print(f"V7 replay fidelity: {'PASS' if r['V7_ok'] else 'FAIL'} " + ", ".join(f"{d} {a}/{b}" for d, a, b in r["V7"]))
    print(f"V8 public privacy: {'PASS' if r['V8_hits'] == 0 else 'FAIL'} ({r['V8_hits']} URL/email hits; names: airbag)")
    s = r["S1"]
    print(f"S1 spine fidelity: {'PASS' if s['ok'] else 'FAIL'} (ledger {s['ledger_submitted']} submitted, "
          f"spine {s['spine'].get('submitted', s['spine'].get('error'))}; fold took {s['spine'].get('ms')} ms)")
    if "--save" in argv:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        p = os.path.join(ROOT, "docs", "bench", "alive.md")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not os.path.exists(p):
            open(p, "w", encoding="utf-8").write(
                "# ALIVE benchmarks (docs/ALIVE_PLAN.md §6)\n\nOne row per phase. A phase that regresses a number does not ship.\n\n"
                "| Date | Phase | Commit | Events | V6 unknown | V7 | V8 hits | S1 ledger/spine | Fold ms |\n|---|---|---|---|---|---|---|---|---|\n")
        open(p, "a", encoding="utf-8").write(
            f"| {time.strftime('%Y-%m-%d')} | {os.environ.get('ALIVE_PHASE', '0')} | {commit} | {r['events']} | "
            f"{len(r['V6_unknown'])} | {'pass' if r['V7_ok'] else 'FAIL'} | {r['V8_hits']} | "
            f"{s['ledger_submitted']}/{s['spine'].get('submitted')} | {s['spine'].get('ms')} |\n")
    return 0 if (not r["V6_unknown"] and r["V7_ok"] and r["V8_hits"] == 0 and s["ok"]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
