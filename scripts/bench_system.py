"""System benchmarks: each one measures a component against a baseline or a corpus, so missing pieces show up as
numbers. Add a benchmark whenever a new failure mode is found (see docs/wiki/Benchmarks.md).

    python scripts/bench_system.py            # all benchmarks, JSON summary on the last line

B1 select   : lazy-heap top-k with freshness bands vs full sort, synthetic queue of 50k jobs (same picks, less time)
B2 answers  : share of every question the engine ever stopped on that the current rules + saved answers can answer
              now (corpus = NEEDS YOU details in events.jsonl). Unanswered, non-legal questions = missing components.
B3 claims   : 8 worker threads race to claim 200 inbox batches; every batch must be claimed exactly once
B4 coverage : median share of your JD terms that reach the resume, from the last 200 resume events
"""
import heapq, json, os, random, statistics, sys, tempfile, threading, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def b1_select(n=50000, k=100, seed=7):
    rnd = random.Random(seed)
    jobs = [(rnd.randint(0, 3), -rnd.random() * 20, i) for i in range(n)]  # (band, -score, id)
    t = time.perf_counter(); full = sorted(jobs)[:k]; t_sort = time.perf_counter() - t
    t = time.perf_counter(); h = list(jobs); heapq.heapify(h); lazy = [heapq.heappop(h) for _ in range(k)]
    t_heap = time.perf_counter() - t
    assert full == lazy
    return {"n": n, "k": k, "sort_ms": round(t_sort * 1e3, 1), "heap_ms": round(t_heap * 1e3, 1),
            "speedup": round(t_sort / t_heap, 1)}


def b2_answers():
    from engine.config import WORKSPACE
    from engine.feedback.answers import missing_questions, LEGAL_OR_SENSITIVE
    from engine.apply.runner import answer_for, autofill_yesno
    p = os.path.join(WORKSPACE, "events.jsonl")
    qs = set()
    for line in open(p, encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("kind") == "application":
            qs.update(missing_questions(e.get("detail") or e.get("status") or ""))
    qs = {q for q in qs if " needs you: " not in q}
    legal = {q for q in qs if LEGAL_OR_SENSITIVE.search(q)}
    rest = qs - legal
    ok = {q for q in rest if answer_for(q, {}) not in (None, "") or autofill_yesno(q)}
    missing = sorted(rest - ok)
    return {"questions": len(qs), "legal_user_only": len(legal), "answerable_now": len(ok),
            "answerable_pct": round(100 * len(ok) / max(1, len(rest)), 1), "missing_sample": [m[:80] for m in missing[:8]]}


def b3_claims(workers=8, batches=200):
    from engine.apply import worker as W
    d = tempfile.mkdtemp()
    W.DIRS = {k: os.path.join(d, k) for k in ("inbox", "claimed", "done")}
    os.makedirs(W.DIRS["inbox"])
    for i in range(batches):
        open(os.path.join(W.DIRS["inbox"], f"b{i:04}.json"), "w").write("[]")
    got, lock = [], threading.Lock()

    def run():
        while True:
            n = W.claim()
            if not n:
                return
            with lock:
                got.append(n)
    ts = [threading.Thread(target=run) for _ in range(workers)]
    t = time.perf_counter(); [x.start() for x in ts]; [x.join() for x in ts]
    return {"workers": workers, "batches": batches, "claimed": len(got), "unique": len(set(got)),
            "exactly_once": len(got) == len(set(got)) == batches, "ms": round((time.perf_counter() - t) * 1e3, 1)}


def b4_coverage(last=200):
    import ast
    from engine.config import WORKSPACE
    vals, ats = [], []
    for line in open(os.path.join(WORKSPACE, "events.jsonl"), encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("kind") == "resume" and e.get("coverage"):
            c = e["coverage"]
            c = ast.literal_eval(c) if isinstance(c, str) else c
            have = len(c.get("jd_terms_you_have") or [])
            if have:
                vals.append(100 * (have - len(c.get("missing_from_resume") or [])) / have)
                ats.append((c.get("ats") or {}).get("score", 0))
    vals, ats = vals[-last:], ats[-last:]
    return {"resumes": len(vals), "median_coverage_pct": round(statistics.median(vals), 1) if vals else None,
            "full_coverage_pct": round(100 * sum(v >= 99.9 for v in vals) / max(1, len(vals)), 1),
            "median_ats_readback": statistics.median(ats) if ats else None}


if __name__ == "__main__":
    out = {}
    for name, fn in (("B1_select", b1_select), ("B2_answers", b2_answers), ("B3_claims", b3_claims), ("B4_coverage", b4_coverage)):
        try:
            out[name] = fn()
        except Exception as e:  # a benchmark that can't run is itself a finding
            out[name] = {"error": str(e)[:120]}
        print(name, json.dumps(out[name]))
    print(json.dumps(out))
