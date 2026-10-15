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


def b8_supervisor():
    """Supervisor decisions against a faked Docker API in a temp workspace: scale up to the backlog, drain before
    stopping, never stop an applier mid-form, refuse unbounded / unlisted creates, stop undeclared containers.
    Each scenario is pass/fail; a failure names itself. Runs in the eval container (module state is patched)."""
    from engine import supervisor as S
    d = tempfile.mkdtemp()
    keep = {k: getattr(S, k) for k in ("FLEET", "BOX", "WORKSPACE", "_docker", "appliers", "clone", "audit")}
    S.FLEET, S.BOX, S.WORKSPACE = os.path.join(d, "fleet"), os.path.join(d, "batches"), d
    for sub in ("inbox", "claimed"):
        os.makedirs(os.path.join(S.BOX, sub))
    os.makedirs(S.FLEET)
    calls, made = [], []
    S._docker = lambda m, p, b=None: calls.append((m, p)) or []
    S.audit = lambda *a, **k: None
    S.clone = lambda *a: made.append(1) or "new"
    a, b = "a" * 64, "b" * 64
    rows = [(a, "deploy-applier-1", True), (b, "deploy-applier-2", True)]
    S.appliers = lambda: rows

    def beat(h, st):
        json.dump({"role": "applier", "host": h, "state": st, "ts": time.time()},
                  open(os.path.join(S.FLEET, f"applier_{h}.json"), "w"))

    def backlog(n):
        for f in os.listdir(os.path.join(S.BOX, "inbox")):
            os.remove(os.path.join(S.BOX, "inbox", f))
        if n:
            json.dump([{}] * n, open(os.path.join(S.BOX, "inbox", "x.json"), "w"))
    out, t0 = {}, time.perf_counter()
    try:
        beat(a[:12], "watching"); beat(b[:12], "applying")
        backlog(12); S.scale(1, 7, _idle={})
        out["scale_up_to_backlog"] = len(made) == 2  # 12 jobs -> want 4, 2 running
        backlog(0); calls.clear(); beat(b[:12], "watching")
        S.scale(1, 7, idle_grace=0, _idle={})
        out["drain_before_stop"] = os.path.exists(S.drain_path(b[:12])) and not calls
        beat(b[:12], "applying"); S.scale(1, 7, idle_grace=0, _idle={})
        out["never_stop_mid_form"] = not any(m == "POST" and "/stop" in p for m, p in calls)
        beat(b[:12], "draining"); S.scale(1, 7, idle_grace=0, _idle={})
        out["stop_after_drain_ack"] = any("/stop" in p for _, p in calls) and any(m == "DELETE" for m, _ in calls)
        body = {"Labels": {"com.docker.compose.service": "applier"}, "HostConfig": {}}
        refused = 0
        for bad, n in ((dict(body, Labels={"com.docker.compose.service": "pipeline"}), 0), (body, S.HARD_MAX),
                       (dict(body, HostConfig={"Binds": ["/var/run/docker.sock:/var/run/docker.sock"]}), 0)):
            try:
                S.bound(bad, n)
            except S.Refused:
                refused += 1
        out["refuse_unsafe_creates"] = refused == 3
        hc = S.bound(body, 0)["HostConfig"]
        out["caps_on_every_create"] = all(hc.get(k) for k in S.CAPS["applier"]) and hc["Privileged"] is False
        S._docker = lambda m, p, b=None: (calls.append((m, p)) or
                                          ([{"Id": "f" * 64, "Names": ["/x"], "State": "running",
                                             "Labels": {"com.docker.compose.service": "miner"}}]
                                           if p.startswith("/containers/json") else {}))
        calls.clear(); S.enforce()
        out["stop_undeclared"] = any(p.endswith("/stop?t=10") for _, p in calls)
    finally:
        for k, v in keep.items():
            setattr(S, k, v)
    ok = [k for k, v in out.items() if v]
    return {"passed": len(ok), "total": len(out), "failed": [k for k, v in out.items() if not v],
            "ms": round((time.perf_counter() - t0) * 1e3, 1)}


API_PATHS = ("/api/health", "/api/control/fleet", "/api/control/bench", "/api/control/reach", "/api/applications",
             "/api/snapshot")


def b9_api(n=20, base=None):
    """API latency: n GETs per endpoint against the running api container; p50 / p95 ms each and overall.
    Skipped (not failed) when the API is unreachable, e.g. a bench run outside the stack."""
    import urllib.request, urllib.error
    base = base or os.environ.get("REGEN_API_URL", "http://api:8787")
    per, every = {}, []
    for p in API_PATHS:
        lat = []
        for _ in range(n):
            t = time.perf_counter()
            try:
                urllib.request.urlopen(base + p, timeout=10).read()
            except urllib.error.HTTPError:
                pass  # answered (404 on an endpoint this build lacks still measures the server)
            except Exception as e:
                if not every and not lat and p == API_PATHS[0]:
                    return {"skipped": f"api unreachable at {base}: {str(e)[:60]}"}
                break
            lat.append((time.perf_counter() - t) * 1e3)
        if lat:
            lat.sort()
            per[p] = {"p50": round(lat[len(lat) // 2], 1), "p95": round(lat[int(0.95 * (len(lat) - 1))], 1)}
            every += lat
    every.sort()
    return {"n": len(every), "p50_ms": round(every[len(every) // 2], 1) if every else None,
            "p95_ms": round(every[int(0.95 * (len(every) - 1))], 1) if every else None, "endpoints": per}


def b10_bus(timeout=20):
    """Data-bus latency: append one `eval_ping` event to events.jsonl, then poll Postgres until the ledger copied
    it (the ledger copies new bytes every 2 s and NOTIFY wakes the API). Skipped without a database."""
    try:
        import psycopg
        from apps.api.store import _dsn
    except Exception as e:
        return {"skipped": f"no psycopg / store: {str(e)[:60]}"}
    dsn = _dsn()
    if not dsn:
        return {"skipped": "no database configured (REGEN_DB_HOST)"}
    from engine.feedback.events import record
    nonce = os.urandom(6).hex()
    t = time.perf_counter()
    record("eval_ping", nonce=nonce)
    with psycopg.connect(dsn) as con:
        while time.perf_counter() - t < timeout:
            if con.execute("SELECT 1 FROM events WHERE kind = 'eval_ping' AND payload->>'nonce' = %s", (nonce,)).fetchone():
                return {"latency_ms": round((time.perf_counter() - t) * 1e3), "ok": True}
            time.sleep(0.1)
    return {"ok": False, "latency_ms": None, "note": f"not in Postgres after {timeout} s"}


BENCHES = (("B1_select", b1_select), ("B2_answers", b2_answers), ("B3_claims", b3_claims), ("B4_coverage", b4_coverage),
           ("B5_rate", b5_rate), ("B6_codes", b6_codes), ("B7_fitgate", b7_fitgate), ("B8_supervisor", b8_supervisor),
           ("B9_api", b9_api), ("B10_bus", b10_bus))


def summary(out):
    """The few numbers worth a ledger row per run (the full results stay in workspace/bench/<stamp>.json)."""
    g = lambda b, k: (out.get(b) or {}).get(k)
    return {"answerable_pct": g("B2_answers", "answerable_pct"), "claims_exactly_once": g("B3_claims", "exactly_once"),
            "coverage_pct": g("B4_coverage", "median_coverage_pct"), "best_per_h": g("B5_rate", "best_per_h"),
            "code_median_s": g("B6_codes", "median_s"), "fit_catch_pct": g("B7_fitgate", "catch_rate_pct"),
            "fit_cost_pct": g("B7_fitgate", "would_block_ok_pct"),
            "supervisor": f"{g('B8_supervisor', 'passed')}/{g('B8_supervisor', 'total')}",
            "api_p95_ms": g("B9_api", "p95_ms"), "bus_ms": g("B10_bus", "latency_ms"),
            "errors": [k for k, v in out.items() if isinstance(v, dict) and "error" in v]}


def history(n=30):
    """The last n saved runs, oldest first: (ts, reason, summary) per run, for the evals page. O(files)."""
    import glob
    from engine.config import WORKSPACE
    rows = []
    for f in sorted(glob.glob(os.path.join(WORKSPACE, "bench", "2*.json")))[-n:]:
        try:
            r = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows.append({"ts": r.get("ts"), "reason": r.get("reason"), "sha": r.get("sha"),
                     "summary": r.get("summary") or summary(r.get("results") or {})})
    return rows


def save(out, reason=None, sha=None):
    from engine.config import WORKSPACE
    d = os.path.join(WORKSPACE, "bench")
    os.makedirs(d, exist_ok=True)
    rec = {"ts": time.time(), "reason": reason, "sha": sha, "summary": summary(out), "results": out}
    stamp = time.strftime("%Y%m%d_%H%M%S")
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
    arg = lambda k: argv[argv.index(k) + 1] if k in argv and len(argv) > argv.index(k) + 1 else None
    if "--save" in argv:
        rec = save(out, reason=arg("--reason"), sha=arg("--sha"))
        from engine.feedback.events import record
        record("eval", reason=rec["reason"], sha=rec["sha"], **rec["summary"])  # one row per run in Postgres
    return out


if __name__ == "__main__":
    main()
