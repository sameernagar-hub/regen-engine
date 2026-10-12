"""Orchestration pipeline: one command from "what's new" to verified submissions.

    python -m engine run [--days 1] [--max 30] [--appliers 2] [--tabs 3] [--no-scan] [--dry] [--loop MIN]

Stages (each logs a `pipeline` event, so a run is traceable end to end):
  1. discover   scan every board for the last N days (Ashby skipped while its bot-check cooldown runs)
  2. select     queue -> not applied, not already waiting on you, at most 3 per company, newest first, interleaved
  3. build      fit gate + one Fact-Bank resume per job (job descriptions fetched in parallel threads)
  4. apply      the batch split across P applier processes, each with its own browser profile and T round-robin tabs
  5. report     verified submissions (proof on disk) for today

Why processes for appliers and threads for fetching: fetching JDs is pure network wait (threads are enough and
cheap); a Playwright browser profile can't be shared, so parallel appliers are separate processes, each running
the round-robin scheduler inside. Greenhouse email codes still come from Gmail (engine/discovery/gmail_codes.js +
`engine codes`), so an operator or agent watches `workspace/codes/` while appliers run.

Complexity: select is O(Q) over the queue with O(1) set lookups; split is O(J). Wall time ≈ build + max over
appliers of their batch time, instead of the sum.
"""
import collections, heapq, datetime, json, os, subprocess, sys, time

from engine.config import ROOT, WORKSPACE, in_workspace
from engine.feedback.events import read, record


def _arg(argv, name, default, cast=int):
    if name in argv:
        return cast(argv[argv.index(name) + 1])
    return default


RETRYABLE = ("EMAIL CODE REQUIRED (timed out)", "no confirmation seen")  # transient: worth one more attempt


def latest_status():
    """url -> latest status; a FAILED that was only a code timeout / missing confirmation (first time) reads as
    RETRY so the selector gives it one more pass while someone is watching the inbox. O(E)."""
    out, fails = {}, collections.Counter()
    for e in read("application"):
        if not e.get("dry") and e.get("url"):
            st = (e.get("status") or "").split(":")[0]
            if st == "FAILED":
                fails[e["url"]] += 1
                if fails[e["url"]] == 1 and any(r in (e.get("detail") or "") for r in RETRYABLE):
                    st = "RETRY"
            elif st == "NEEDS YOU" and answerable_now(e.get("detail") or ""):
                st = "RETRY"
            out[e["url"]] = st
    return out


def answerable_now(detail):
    """True when a NEEDS YOU job can be finished today without the user: it was only parked for the Ashby cooldown
    (never opened), or every question it stopped on now has an answer (a new rule, preset or saved answer).
    Legal / sensitive questions never count as answerable. O(questions x rules)."""
    if "cooldown" in detail:  # never opened, or filled and parked (18 on 10-11): refill once the cooldown ends
        return True  # the selector still skips Ashby while the cooldown runs, and takes 1 Ashby job per pass
    from engine.feedback.answers import LEGAL_OR_SENSITIVE, missing_questions
    qs = missing_questions(detail)
    if not qs or any(LEGAL_OR_SENSITIVE.search(q) for q in qs):
        return False
    from engine.apply.runner import answer_for
    return all(answer_for(q, {}) not in (None, "") for q in qs)


SKIP_ATS = {a.strip() for a in os.environ.get("REGEN_SKIP_ATS", "").split(",") if a.strip()}
WALL = ("CAPTCHA", "BOT-CHECK")  # failure details that mean "a human must finish this", not "retry"
HUMAN_ONLY = ("arbitration", "assessment", "transcript", "export c", "any disputes")  # blockers only the user can clear ("any disputes": an arbitration clause cut at 100 chars)


def ats_of(url):
    """ATS key from a posting URL (greenhouse / ashby / lever / workable / other)."""
    u = url or ""
    return next((k for k, m in (("greenhouse", "greenhouse"), ("ashby", "ashbyhq"), ("lever", "lever.co"), ("workable", "workable"))
                 if m in u), "other")


def history(days=3, min_tries=4, wall_rate=0.5):
    """Learn from recent attempts so a run only opens forms it can finish (the 100%-completion goal).

    Returns (walled_ats, blocked_companies):
      walled_ats         ATSs where at least `wall_rate` of the last `days` days' attempts hit a captcha / bot-check
                         (seen 10-09: one ATS asked for hCaptcha on 6 of 6 jobs) -> left for the user's assist list
      blocked_companies  companies whose last attempt stopped on something only the user can clear (arbitration,
                         assessments, transcripts, export-control self-certification) or a captcha
    One pass over the application events: O(E) time, O(companies) space."""
    since = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    tries, walls, blocked = collections.Counter(), collections.Counter(), set()
    for e in read("application"):
        if e.get("dry") or (e.get("ts") or "") < since:
            continue
        detail = e.get("detail") or ""
        if "cooldown" in detail.lower():
            continue  # never opened: says nothing about the ATS
        a = ats_of(e.get("url"))
        tries[a] += 1
        if any(w in detail for w in WALL):
            walls[a] += 1
        co = (e.get("job") or "").split(" - ")[0].strip().lower()
        if co and (any(w in detail for w in WALL) or any(h in detail.lower() for h in HUMAN_ONLY)):
            blocked.add(co)
    walled = {a for a in tries if tries[a] >= min_tries and walls[a] / tries[a] >= wall_rate}
    return walled, blocked


ASHBY_PER_PASS = int(os.environ.get("REGEN_ASHBY_PER_PASS", "1"))


def select(queue, max_jobs, ashby_ok=True, per_company=3):
    """Highest-priority jobs (engine/discovery/priority.py) that were never tried (or only hit a transient failure),
    capped per company, interleaved by company."""
    st = latest_status()
    walled, blocked = history()
    if walled:
        print(f"select: skipping {', '.join(sorted(walled))} (captcha walls on most recent attempts; see the assist list)")
    from engine.discovery.priority import band, lane_rates, score
    rates = lane_rates()
    # freshness bands first (past hour > day > week > older), score inside a band. Lazy heap: O(Q) heapify, then
    # O(log Q) per job popped; only as many pops as needed to fill max_jobs (skips are cheap), not a full sort.
    heap = [(band(j), -score(j, rates)[0], i) for i, j in enumerate(queue)]
    heapq.heapify(heap)
    per, picked = collections.Counter(), []
    seen = {(e.get("job") or "").lower().strip() for e in read("application")
            if not e.get("dry") and (e.get("status") or "").startswith("SUBMITTED")}
    while heap:
        j = queue[heapq.heappop(heap)[2]]
        key = f"{j['company']} - {j['title']}".lower().strip()
        if key in seen:
            continue  # one posting listed under several URLs (locations, sources): 10-11 batch held the same role 3 times
        seen.add(key)
        if st.get(j["url"]) in ("SUBMITTED", "SKIPPED", "NEEDS YOU", "FLAGGED", "FAILED"):
            continue  # FAILED too: a failed form stays filled-in on the assist list instead of being retried blind
        if not ashby_ok and j.get("ats") == "ashby":
            continue
        if j.get("ats") in SKIP_ATS or j.get("ats") in walled:  # REGEN_SKIP_ATS, or learned from captcha walls
            continue
        co = j["company"].lower()
        if co in blocked:
            continue  # this company is waiting on the user (arbitration, assessment, captcha)
        if per[co] >= per_company:
            continue
        if j.get("ats") == "ashby":  # Ashby bot-flags bursts (5 parallel workers tripped it on 10-10): a few per hour
            if per["__ashby__"] >= ASHBY_PER_PASS:
                continue
            per["__ashby__"] += 1
        per[co] += 1
        picked.append(j)
        if len(picked) >= max_jobs:
            break
    from engine.apply.runner import interleave
    return interleave([dict(j, name=f"{j['company']} - {j['title']}") for j in picked])


def prune(queue):
    """Drop queue jobs that can never be applied to by the engine (final status, skipped or captcha-walled ATS) and
    rewrite queue.json, so the queue holds only fillable jobs (user, 2026-10-10). NEEDS YOU stays: answers re-open it.
    O(Q)."""
    st = latest_status()
    walled, _ = history()
    keep = [j for j in queue if st.get(j["url"]) not in ("SUBMITTED", "SKIPPED", "FLAGGED", "FAILED")
            and j.get("ats") not in SKIP_ATS and j.get("ats") not in walled]
    if len(keep) != len(queue):
        json.dump(keep, open(os.path.join(WORKSPACE, "queue.json"), "w", encoding="utf-8"), indent=1)
        print(f"prune: {len(queue) - len(keep)} unusable jobs dropped, {len(keep)} kept")
    return keep


def split(jobs, parts):
    """Round-robin split so each applier gets a mix of companies and ATSs. O(J)."""
    out = [[] for _ in range(max(1, parts))]
    for i, j in enumerate(jobs):
        out[i % len(out)].append(j)
    return [b for b in out if b]


def run(days=1, max_jobs=30, appliers=2, tabs=3, scan=True, dry=False):
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    t0 = time.monotonic()
    with in_workspace():
        from engine.apply.runner import ashby_cooling
        ashby_ok = not ashby_cooling()
    if scan:
        ats = "greenhouse,ashby,lever,workable" if ashby_ok else "greenhouse,lever,workable"
        subprocess.run([sys.executable, "-m", "engine", "scan", str(days), "--ats", ats], cwd=ROOT, check=False)
    q = prune(json.load(open(os.path.join(WORKSPACE, "queue.json"), encoding="utf-8")))
    chosen = select(q, max_jobs, ashby_ok)
    record("pipeline", stage="select", queued=len(q), chosen=len(chosen), ashby=ashby_ok)
    print(f"select: {len(chosen)} of {len(q)} queued jobs" + ("" if ashby_ok else " (Ashby cooling down: skipped)"))
    if not chosen:
        return []
    from engine.tailoring.batch import build
    batch = build(f"run_{stamp}", [str(j["id"]) for j in chosen])
    record("pipeline", stage="build", jobs=len(batch))
    # hybrid scale-out: REGEN_DOCKER_PARTS=K extra parts go to container workers (engine/apply/worker.py) while
    # `appliers` local browsers take the rest; REGEN_APPLIERS=docker sends everything to the containers.
    k = int(os.environ.get("REGEN_DOCKER_PARTS") or 0)
    local_n = 0 if os.environ.get("REGEN_APPLIERS") == "docker" else appliers
    parts = split(batch, local_n + (k or (appliers if not local_n else 0)))
    boxed = _drop(parts[local_n:], stamp, local_n)
    procs = []
    for i, part in enumerate(parts[:local_n]):
        name = f"run_{stamp}_{i}"
        path = os.path.join(WORKSPACE, "batches", name + ".json")
        json.dump(part, open(path, "w"), indent=1)
        env = dict(os.environ, REGEN_TABS=str(tabs), PYTHONUNBUFFERED="1",
                   REGEN_PW_PROFILE="pw-profile" if i == 0 else f"pw-profile-{i + 1}")
        log = open(os.path.join(WORKSPACE, "logs", name + ".log"), "w", encoding="utf-8")
        args = [sys.executable, "-m", "engine", "apply", f"batches/{name}.json"] + (["--dry"] if dry else [])
        procs.append((name, subprocess.Popen(args, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)))
        print(f"apply: {name} -> {len(part)} jobs, {tabs} tabs, log workspace/logs/{name}.log")
    record("pipeline", stage="apply", appliers=[n for n, _ in procs], jobs=len(batch))
    for _, p in procs:
        p.wait()
    _wait(boxed)
    st = latest_status()
    done = [j for j in batch if st.get(j["url"]) == "SUBMITTED"]
    record("pipeline", stage="report", submitted=len(done), jobs=len(batch), wall_s=round(time.monotonic() - t0, 1))
    print(f"report: {len(done)} of {len(batch)} submitted in {time.monotonic() - t0:.0f}s")
    return done


def _drop(parts, stamp, offset):
    """Write each part into batches/inbox/ (atomic rename) for the container workers. Returns the file names."""
    from engine.apply.worker import DIRS
    for d in DIRS.values():
        os.makedirs(d, exist_ok=True)
    names = []
    for i, part in enumerate(parts, offset):
        name = f"run_{stamp}_{i}.json"
        tmp = os.path.join(DIRS["inbox"], "." + name)
        json.dump(part, open(tmp, "w"), indent=1)
        os.replace(tmp, os.path.join(DIRS["inbox"], name))  # appear atomically: a worker never reads half a file
        names.append(name)
        print(f"dispatch: {name} -> {len(part)} jobs -> batches/inbox (container worker)")
    if names:
        record("pipeline", stage="dispatch", parts=names)
    return names


def _wait(names, timeout_h=3):
    """Block until every dispatched part is in batches/done/ (or the timeout: a dead worker never stalls the loop)."""
    from engine.apply.worker import DIRS
    end = time.monotonic() + timeout_h * 3600
    while names and time.monotonic() < end and not all(os.path.exists(os.path.join(DIRS["done"], n)) for n in names):
        time.sleep(5)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    os.makedirs(os.path.join(WORKSPACE, "logs"), exist_ok=True)
    kw = dict(days=_arg(argv, "--days", 1, float), max_jobs=_arg(argv, "--max", 30), appliers=_arg(argv, "--appliers", 2),
              tabs=_arg(argv, "--tabs", 3), scan="--no-scan" not in argv, dry="--dry" in argv)
    loop = _arg(argv, "--loop", 0, float)  # minutes; 0 = one pass
    if not loop:
        run(**kw)
        return
    # first-applicant mode: after the first full pass, rescan only the last few hours every `loop` minutes and apply
    # to whatever just opened. Runs until stopped (Ctrl+C or the control room's Stop): started by the user, never scheduled.
    n = 0
    while True:
        run(**dict(kw, days=kw["days"] if n == 0 else max(loop / 1440 * 3, 0.125)))
        n += 1
        try:  # disk hygiene every pass: logged proofs/resumes/caches past their window (engine/clean.py)
            from engine.clean import main as clean
            clean([])
        except Exception as e:  # never let cleanup stop applying
            print(f"clean skipped: {e}")
        print(f"loop: pass {n} done; next scan in {loop:g} min", flush=True)
        time.sleep(loop * 60)
