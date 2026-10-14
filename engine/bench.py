"""System benchmarks: each one measures a component against a baseline or a corpus, so missing pieces show up as
numbers. Add a benchmark whenever a new failure mode is found (see docs/wiki/Benchmarks.md).

    python -m engine bench [--save]           # all benchmarks, JSON summary on the last line
    python scripts/bench_system.py            # same (thin wrapper kept for old docs and notes)

--save writes workspace/bench/<stamp>.json and workspace/bench/latest.json (GET /api/control/bench, the control
room's Benchmarks card). The supervisor runs `bench --save` in a subprocess every BENCH_HOURS (B3 swaps the worker's
inbox dirs for temp ones, so it must never run inside a long-lived process).

B1 select   : lazy-heap top-k with freshness bands vs full sort, synthetic queue of 50k jobs (same picks, less time)
B2 answers  : share of every question the engine ever stopped on that the current rules + saved answers can answer
              now (corpus = NEEDS YOU details in events.jsonl). Unanswered, non-legal questions = missing components.
B3 claims   : 8 worker threads race to claim 200 inbox batches; every batch must be claimed exactly once
B4 coverage : median share of your JD terms that reach the resume, from the last 200 resume events
B5 rate     : verified submissions per active hour (an hour with any application attempt), per day, from events.jsonl
B6 codes    : email-code latency, .wait written -> .txt delivered (workspace/codes), and how many waits never got one
B7 fit gate : today's fit() re-run on the stored JD of every submitted job: share of later rejections it would now
              block (catch rate) vs share of not-rejected submissions it would block (cost). A missed blocker = a rule.
"""
import heapq, json, os, random, statistics, sys, tempfile, threading, time


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


def _events(kind):
    from engine.config import WORKSPACE
    for line in open(os.path.join(WORKSPACE, "events.jsonl"), encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("kind") == kind:
            yield e


def b5_rate():
    import collections
    hours, subs = collections.defaultdict(set), collections.Counter()
    for e in _events("application"):
        if e.get("dry") or not e.get("ts"):
            continue
        day, hour = e["ts"][:10], e["ts"][11:13]
        hours[day].add(hour)
        subs[day] += (e.get("status") or "").startswith("SUBMITTED")
    days = sorted(hours)[-7:]
    per = {d: {"submitted": subs[d], "active_h": len(hours[d]), "per_h": round(subs[d] / len(hours[d]), 2)} for d in days}
    best = max(per.values(), key=lambda x: x["per_h"]) if per else None
    return {"days": per, "best_per_h": best and best["per_h"]}


def b6_codes():
    lat = [e["latency_s"] for e in _events("code") if isinstance(e.get("latency_s"), (int, float))]
    lost = sum("EMAIL CODE REQUIRED" in (e.get("detail") or "") for e in _events("application"))
    return {"delivered": len(lat), "code_timeouts": lost,
            "median_s": round(statistics.median(lat)) if lat else None,
            "p90_s": round(sorted(lat)[int(0.9 * (len(lat) - 1))]) if lat else None}


def b7_fitgate():
    import glob, html as H
    from engine.config import WORKSPACE
    from engine.tailoring.tailor import fit
    jd = {}
    for f in glob.glob(os.path.join(WORKSPACE, "jd", "*.json")):
        try:
            j = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        url = (j.get("absolute_url") or j.get("jobUrl") or j.get("applyUrl") or "").split("?")[0]
        text = j.get("content") or j.get("descriptionHtml") or j.get("descriptionPlain") or j.get("description") or ""
        if url and text:
            jd[url] = H.unescape(text)
    url_of = {}
    for e in _events("application"):
        if (e.get("status") or "").startswith("SUBMITTED") and e.get("url"):
            url_of[e["job"]] = e["url"].split("?")[0]
    rejected = {j for e in _events("outcome") if e.get("outcome") == "rejection" for j in (e.get("jobs") or [])}
    rej, ok = [], []
    for job, url in url_of.items():
        if url in jd:
            (rej if job in rejected else ok).append(bool(fit(jd[url])))
    return {"submitted_with_jd": len(rej) + len(ok), "rejections_with_jd": len(rej),
            "catch_rate_pct": round(100 * sum(rej) / len(rej), 1) if rej else None,
            "would_block_ok_pct": round(100 * sum(ok) / len(ok), 1) if ok else None}


BENCHES = (("B1_select", b1_select), ("B2_answers", b2_answers), ("B3_claims", b3_claims), ("B4_coverage", b4_coverage),
           ("B5_rate", b5_rate), ("B6_codes", b6_codes), ("B7_fitgate", b7_fitgate))


def save(out):
    from engine.config import WORKSPACE
    d = os.path.join(WORKSPACE, "bench")
    os.makedirs(d, exist_ok=True)
    rec = {"ts": time.time(), "results": out}
    stamp = time.strftime("%Y%m%d_%H%M")
    for name in (f"{stamp}.json", "latest.json"):
        tmp = os.path.join(d, "." + name)
        json.dump(rec, open(tmp, "w", encoding="utf-8"), indent=1)
        os.replace(tmp, os.path.join(d, name))
    return rec


def latest():
    from engine.config import WORKSPACE
    try:
        return json.load(open(os.path.join(WORKSPACE, "bench", "latest.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out = {}
    for name, fn in BENCHES:
        try:
            out[name] = fn()
        except Exception as e:  # a benchmark that can't run is itself a finding
            out[name] = {"error": str(e)[:120]}
        print(name, json.dumps(out[name]))
    print(json.dumps(out))
    if "--save" in argv:
        save(out)
    return out


if __name__ == "__main__":
    main()
