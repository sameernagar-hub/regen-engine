"""v0.10 control room API: start/stop runs with filters, watch every stage while it processes, see the Fact Bank,
open any resume that was sent. Reads are local evidence; writes (run, stop, filters) need REGEN_API_WRITE=1 and
a request from this computer, like POST /api/answers.
"""
import collections, json, os, re, shutil, time, urllib.parse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from engine import control as C
from engine.config import WORKSPACE, profile_file

router = APIRouter(prefix="/api")
from engine.notify import _env as _local_env
WRITE = _local_env().get("REGEN_API_WRITE") == "1"  # env var, or REGEN_API_WRITE=1 in the git-ignored .env
LOCAL = ("127.0.0.1", "::1", "localhost", "testclient")


def _guard(request: Request):
    if not WRITE:
        raise HTTPException(403, "writes are disabled (set REGEN_API_WRITE=1 on your own machine)")
    if (request.client.host if request.client else "") not in LOCAL:
        raise HTTPException(403, "only from this computer")


def _tail(path, n=40):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 16000))
            return f.read().decode("utf-8", "replace").splitlines()[-n:]
    except OSError:
        return []


APPLIER_LINE = re.compile(r"^\[([^\]]+)\] (?:== (.+)|-> ([A-Z ]+?)(?::|$)(.*)|\. (.{0,60}?) -> (.*))$")


def _applier(path):
    """One applier log -> what it is doing right now: current jobs per tab, last answers, results so far."""
    lines = _tail(path, 400)
    jobs, results, qa = {}, collections.Counter(), []
    for l in lines:
        m = APPLIER_LINE.match(l.strip())
        if not m:
            continue
        slug, start, status, detail, q, a = m.groups()
        if start:
            jobs[slug] = {"job": start.strip(), "state": "filling"}
        elif status:
            results[status.strip()] += 1
            jobs.setdefault(slug, {"job": slug})["state"] = status.strip()
        elif q:
            qa.append({"job": slug, "q": q.strip(), "a": (a or "").strip()[:80]})
    summary = next((l for l in reversed(lines) if l.startswith("== ") and "jobs in" in l), None)
    return {"name": os.path.basename(path)[:-4], "updated": os.path.getmtime(path), "jobs": list(jobs.values())[-6:],
            "results": dict(results), "answers": qa[-8:], "done": bool(summary), "summary": summary}


LOOP_STAGES = ("discover", "newgrad", "feed")


def _loop_steps(now):
    """Stage status for the pipeline container's loop (`engine run --loop`), read from heartbeats, so the control room
    shows the loop working even when no run was started from the UI. The pipeline beats each step with its `stage`
    (discover, newgrad, feed, apply); between passes, apply stays live while any applier is still filling forms.
    [] when no fresh pipeline heartbeat (the container is down). O(files)."""
    from engine.supervisor import FLEET, STALE
    beats = []
    for f in (os.listdir(FLEET) if os.path.isdir(FLEET) else []):
        if f.endswith(".json") and f.split("_")[0] in ("pipeline", "applier"):
            try:
                beats.append(json.load(open(os.path.join(FLEET, f), encoding="utf-8")))
            except (OSError, ValueError):
                pass
    pipe = [x for x in beats if x.get("role") == "pipeline"]
    b = max(pipe, key=lambda x: x.get("ts", 0), default=None)
    if not b or now - b.get("ts", 0) > STALE["pipeline"]:
        return []
    st, ts = str(b.get("state", "")), b.get("ts")
    stage = b.get("stage") or ("discover" if st.startswith("scanning") else "apply" if st.startswith("waiting") else None)
    applying = any(x.get("state") == "applying" and now - x.get("ts", 0) < STALE["applier"] for x in beats
                   if x.get("role") == "applier")
    order = [*LOOP_STAGES, "apply"]
    out = []
    for k in order:
        if stage in order and order.index(k) < order.index(stage):
            out.append({"name": k, "status": "done"})
        elif k == stage:
            out.append({"name": k, "status": "running", "started": ts, "detail": st})
        elif k == "apply" and applying:  # forms still being filled from the last pass / your /needs answers
            out.append({"name": k, "status": "running", "started": ts, "detail": "appliers filling forms"})
        elif stage is None:  # sleeping between passes: everything finished, next scan soon
            out.append({"name": k, "status": "done"})
        else:
            out.append({"name": k, "status": "waiting"})
    return out


@router.get("/control/state")
def state():
    """The run (if one was started from the UI), every applier active in the last 15 minutes, queue, limits."""
    s = C.read_state()
    if not s.get("running"):  # the pipeline container's loop is the run; show its stages
        loop = _loop_steps(time.time())
        if loop:
            s = dict(s, steps=loop)
    logs = os.path.join(WORKSPACE, "logs")
    now = time.time()
    appliers = []
    if os.path.isdir(logs):
        for f in sorted(os.listdir(logs)):
            p = os.path.join(logs, f)
            if (re.fullmatch(r"run_\d{8}_\d{4}(_w?\d+)?[a-z]?_?\d*b?\.log", f)
                    or re.fullmatch(r"answers_\d{8}_\d{6}\.log", f)) and now - os.path.getmtime(p) < 900:  # + /needs retries
                appliers.append(_applier(p))
    q = []
    try:
        q = json.load(open(os.path.join(WORKSPACE, "queue.json"), encoding="utf-8"))
    except (OSError, ValueError):
        pass
    cool = None
    try:
        t = open(os.path.join(WORKSPACE, "ashby_cooldown")).read().strip()
        cool = time.mktime(time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S")) + 86400
    except (OSError, ValueError):
        pass
    by_ats = collections.Counter(j.get("ats", "?") for j in q)
    return {"run": s, "run_log": _tail(os.path.join(WORKSPACE, s["log"]), 30) if s.get("log") else [],
            "appliers": appliers, "queue": len(q), "queue_by_ats": dict(by_ats),
            "ashby_open_at": cool if cool and cool > now else None, "defaults": C.defaults(),
            "write": WRITE}


@router.get("/control/fleet")
def fleet():
    """Container health from heartbeats in the shared workspace (engine/supervisor.py): pipeline, appliers, relay,
    supervisor (+ the services it probes), batch queue, lost claims, codes waiting, kill switch, applier limits, the
    supervisor's last audit records and which ledger backend the API reads."""
    from apps.api import store
    from engine.supervisor import audit_tail, status
    return dict(status(), audit=audit_tail(12), ledger=store.backend())


@router.get("/control/containers")
def containers():
    """The supervisor's container inventory (service, state, uptime, CPU, memory), refreshed every minute; null
    when the supervisor is not running (only it holds the Docker socket)."""
    from engine.supervisor import containers as inv
    return inv() or {"containers": [], "stale": True}


REACH_WRITE = WRITE or os.environ.get("REGEN_API_REACH") == "1"  # bank: only the reach status write, nothing else
TRUST_PORT = os.environ.get("REGEN_API_TRUST_PORT") == "1"        # published on 127.0.0.1 only (see apps/api/main.py)
REACH_STATUS = {"submitted": "SUBMITTED", "skipped": "SKIPPED", "todo": None}


def _reach_status():
    """url -> (status, ts) of the user's own reach marks (latest wins). O(E)."""
    from engine.feedback.events import read
    out = {}
    for e in read("reach_mark"):
        out[e.get("url")] = (e.get("status"), e.get("ts"))
    return out


@router.get("/control/reach")
def reach(limit: int = 100):
    """Reach list (engine/discovery/reach.py): Workday / iCIMS / SmartRecruiters jobs with a tailored resume, newest
    first, for the user to submit; each row carries the user's own mark (todo / submitted / skipped)."""
    from engine.discovery.reach import load, internal
    rows = load()
    marks = _reach_status()
    live = [dict(r, mark=(marks.get(r["url"]) or ("todo", None))[0], marked=(marks.get(r["url"]) or (None, None))[1])
            for r in rows if r.get("resume") and not internal(r["url"])][::-1]
    by = collections.Counter(r["ats"] for r in live)
    return {"rows": live[:max(1, min(limit, 500))], "listed": len(live), "gated": len(rows) - len(live), "by_ats": dict(by),
            "marks": dict(collections.Counter(r["mark"] for r in live)), "write": REACH_WRITE}


BIG_ROW = re.compile(r"^\| (?P<posted>[^|]*) \| (?P<company>[^|]+) \| \[(?P<title>.+?)\]\((?P<url>[^)]+)\) \| (?P<location>[^|]*) \| "
                     r"(?P<lane>[^|]*) \| (?P<ats>\d+)% \| `(?P<resume>[^`]+)` \|$")
NEW_GRAD = re.compile(r"new (college )?grad|university|early career|entry.?level|graduate|junior|\bi\b|\b1\b", re.I)


@router.get("/control/bigtech")
def bigtech():
    """Big-tech portals (engine/discovery/bigtech.py): roles that passed the title filter and fit gate, each with a
    tailored resume, read from workspace/bigtech.md (newest first). Applying happens on the company's own portal."""
    from engine.discovery import bigtech as B
    p = os.path.join(WORKSPACE, "bigtech.md")
    rows = []
    for line in (open(p, encoding="utf-8").read().splitlines() if os.path.exists(p) else []):
        m = BIG_ROW.match(line.strip())
        if m:
            r = m.groupdict()
            rows.append(dict(r, ats=int(r["ats"]), resume=os.path.basename(r["resume"].replace("\\", "/")),
                             new_grad=bool(NEW_GRAD.search(r["title"]))))
    last = os.path.join(WORKSPACE, "bigtech_last")
    return {"rows": rows, "sources": [s.__name__.capitalize() if s.__name__ != "nvidia" else "NVIDIA" for s in B.SOURCES],
            "by_company": dict(collections.Counter(r["company"] for r in rows)),
            "new_grad": sum(r["new_grad"] for r in rows), "queries": B.BIG_Q,
            "last_run": time.strftime("%Y-%m-%dT%H:%M", time.localtime(os.path.getmtime(last))) if os.path.exists(last) else None}


def _pretty(slug):
    """Board tokens are slugs ("1800contacts", "acme-robotics"): a readable name for the discover orbs."""
    s = re.sub(r"[-_.]+", " ", str(slug).split("/")[0].split(".")[0]).strip()
    return s if any(c.isupper() for c in s) else s.title()


@router.get("/control/discover")
def discover(n: int = 36):
    """What the Discover station is looking at: boards watched per ATS, the six big-tech portals, and `n` orbs, one
    per company with the newest postings in the queue (company, ATS, a role). O(queue)."""
    from engine.discovery.bigtech import SOURCES
    boards = {}
    try:
        b = json.load(open(os.path.join(WORKSPACE, "boards.json"), encoding="utf-8"))
        boards = {k: len(v) for k, v in b.items() if k != "dead"}
    except (OSError, ValueError):
        pass
    try:
        q = json.load(open(os.path.join(WORKSPACE, "queue.json"), encoding="utf-8"))
    except (OSError, ValueError):
        q = []
    orbs, seen = [], set()
    for j in sorted(q, key=lambda j: str(j.get("posted") or ""), reverse=True):
        name = _pretty(j.get("company") or "")
        if name and name.lower() not in seen:
            seen.add(name.lower())
            orbs.append({"company": name, "ats": j.get("ats") or "", "title": j.get("title") or ""})
        if len(orbs) >= max(1, min(n, 80)):
            break
    portals = [s.__name__.capitalize() if s.__name__ != "nvidia" else "NVIDIA" for s in SOURCES]
    return {"boards": boards, "total": sum(boards.values()), "portals": portals, "orbs": orbs}


def _kit_fields():
    """The answers a Workday / iCIMS form asks for, straight from presets + Fact Bank (the same values the engine
    types into Greenhouse/Ashby forms), grouped the way those portals ask. Nothing new is generated."""
    from engine.apply.runner import P, EDU, current_role, fact_bank
    g = lambda k: P.get(k) if not str(P.get(k) or "").startswith("<") else None
    fb = fact_bank()
    roles = []
    for _, r in (fb.get("roles") or {}).items():
        try:
            company, title, where, span = r[:4]
            roles.append({"company": company, "title": title, "location": where, "dates": span})
        except (ValueError, TypeError):
            continue
    cur = current_role(fb) or {}
    return [
        {"group": "Contact", "fields": [["First name", g("first_name")], ["Last name", g("last_name")], ["Email", g("email")],
                                        ["Phone", g("phone")], ["Address line 1", g("address_line1")], ["City", g("city")],
                                        ["State", g("state")], ["ZIP", g("zip")], ["Country", g("country")],
                                        ["LinkedIn", g("linkedin")], ["GitHub", g("github")]]},
        {"group": "Work authorization", "fields": [
            ["Authorized to work in the US?", g("work_authorized_us")],
            ["Require sponsorship now or in the future?", g("needs_sponsorship_now_or_future")],
            ["Authorized without sponsorship (today)?", g("authorized_without_sponsorship")],
            ["Work authorization status", g("work_auth_status")], ["Citizenship", g("citizenship_country")],
            ["US citizen / US person (ITAR)?", g("us_citizen_or_us_person_itar")], ["Security clearance", g("security_clearance")]]},
        {"group": "Education", "fields": [["School", g("school")], ["Degree", g("degree")], ["Major", g("major")],
                                          ["GPA", g("gpa")], ["Start", " ".join(x for x in (EDU.get("start_month"), EDU.get("start_year")) if x) or None],
                                          ["End / graduation", " ".join(x for x in (EDU.get("end_month"), EDU.get("end_year")) if x) or g("grad_year")]]},
        {"group": "Current role", "fields": [["Company", cur.get("company")], ["Title", cur.get("title")],
                                             ["Start", " ".join(x for x in (cur.get("start_month"), cur.get("start_year")) if x) or None],
                                             ["Current role", "Yes" if cur.get("current") else None]]},
        {"group": "Experience (Fact Bank, as written)", "fields": [[f"{r['title']} · {r['company']}", f"{r['dates']} · {r['location']}"] for r in roles]},
        {"group": "Other answers", "fields": [
            ["Years of experience", g("years_experience")], ["Earliest start date", g("start_date")],
            ["Open to onsite / relocation", g("open_to_onsite_or_relocation")], ["Needs relocation assistance", g("needs_relocation_assistance")],
            ["Willing to do a background check", g("willing_background_check")], ["Over 18", g("over_18")],
            ["How did you hear about us", g("how_heard")],
            ["Salary", "the posting's range midpoint; no range: " + str(g("market_salary") or "?")],
            ["Gender / race / veteran / disability", "Decline to answer"]]},
    ]


@router.get("/reach/kit")
def reach_kit(request: Request):
    """Copy-ready answers for filling a Workday / iCIMS application by hand (presets + Fact Bank). Personal data:
    only for this computer (127.0.0.1-published port in the bank, localhost otherwise)."""
    if not TRUST_PORT and (request.client.host if request.client else "") not in LOCAL:
        raise HTTPException(403, "only from this computer")
    return {"groups": [dict(g, fields=[[k, str(v)] for k, v in g["fields"] if v not in (None, "")]) for g in _kit_fields()]}


@router.post("/reach/fill")
def reach_fill(body: dict, request: Request):
    """Queue one reach-list Workday job for the desk (engine/apply/workday.py): the desk opens it in the browser you
    signed in to and fills it. Same switch and same this-computer rule as /reach/mark."""
    if not REACH_WRITE:
        raise HTTPException(403, "reach writes are disabled (REGEN_API_REACH=1 in the bank, REGEN_API_WRITE=1 locally)")
    if not TRUST_PORT and (request.client.host if request.client else "") not in LOCAL:
        raise HTTPException(403, "only from this computer")
    from engine.discovery.reach import load
    from engine.apply.workday import request as queue
    url = str(body.get("url") or "")
    row = next((r for r in load() if r.get("url") == url and r.get("resume")), None)
    if not row:
        raise HTTPException(404, "not on the reach list")
    if row.get("ats") not in ("workday", "smartrecruiters"):
        raise HTTPException(400, f"the desk fills Workday and SmartRecruiters forms; {row.get('ats')} is not supported yet")
    queue(url, f"{row['company']} - {row['title']}", row["resume"])
    from engine.supervisor import fleet
    desk = next((m for m in fleet()["members"] if m.get("role") == "desk"), None)
    return {"ok": True, "queued": url, "desk": "up" if desk and desk.get("up") else "down",
            "open": _desk_url()}


def _desk_url():
    """noVNC link with this start's desk password (workspace/.desk_pass, written by the desk container). Only the local
    control room can read it: CORS + the Host check keep other pages out of this API."""
    url = "http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale"
    try:
        with open(os.path.join(WORKSPACE, ".desk_pass")) as f:
            pw = f.read().strip()
    except OSError:
        return url
    return url + "&password=" + urllib.parse.quote(pw) if pw else url


@router.get("/reach/signins")
def reach_signins():
    """Workday employers to sign in to in the desk, most open reach jobs first (one account per employer host)."""
    from engine.discovery.reach import load, signins
    done = {u for u, (m, _) in _reach_status().items() if m in ("submitted", "skipped")}
    rows = signins(load(), done)
    return {"employers": rows, "jobs": sum(r["jobs"] for r in rows)}


@router.post("/reach/open")
def reach_open(body: dict, request: Request):
    """Open one Workday employer's site in the desk and press its Sign In button, so the user signs in there.
    Only URLs of employers on the sign-in list are accepted (the desk never opens arbitrary pages from the API)."""
    if not REACH_WRITE:
        raise HTTPException(403, "reach writes are disabled (REGEN_API_REACH=1 in the bank, REGEN_API_WRITE=1 locally)")
    if not TRUST_PORT and (request.client.host if request.client else "") not in LOCAL:
        raise HTTPException(403, "only from this computer")
    from engine.discovery.reach import load, signins
    from engine.apply.workday import request as queue
    url = str(body.get("url") or "")
    row = next((e for e in signins(load()) if e["url"] == url), None)
    if not row:
        raise HTTPException(404, "not a Workday employer on the reach list")
    queue(url, f"Sign in: {row['company']}", kind="open")
    return {"ok": True, "opening": url}


@router.get("/reach/desk")
def reach_desk():
    """The desk's heartbeat (ready / filling, queue length, last result) and its latest results per reach URL."""
    from engine.supervisor import fleet
    from engine.feedback.events import read
    desk = next((m for m in fleet()["members"] if m.get("role") == "desk"), None)
    last = {}
    for e in read("application"):
        if e.get("by") == "desk" and e.get("url"):
            last[e["url"]] = {"status": e.get("status"), "detail": e.get("detail"), "ts": e.get("ts"), "proof": e.get("proof")}
    return {"desk": desk, "open": _desk_url(), "results": last}


@router.post("/reach/mark")
def reach_mark(body: dict, request: Request):
    """The user marks a reach job submitted / skipped / back to to-do. Recorded as a `reach_mark` event; "submitted"
    also records an application event (status SUBMITTED, detail "by you on <ats>") so the engine never re-lists or
    re-applies to that role. Needs REGEN_API_REACH=1 (or REGEN_API_WRITE=1) and a request from this computer."""
    if not REACH_WRITE:
        raise HTTPException(403, "reach writes are disabled (REGEN_API_REACH=1 in the bank, REGEN_API_WRITE=1 locally)")
    if not TRUST_PORT and (request.client.host if request.client else "") not in LOCAL:
        raise HTTPException(403, "only from this computer")
    from engine.discovery.reach import load
    from engine.feedback.events import record
    url, mark = str(body.get("url") or ""), str(body.get("mark") or "")
    if mark not in REACH_STATUS:
        raise HTTPException(400, "mark must be submitted, skipped or todo")
    row = next((r for r in load() if r.get("url") == url and r.get("resume")), None)
    if not row:
        raise HTTPException(404, "not on the reach list")
    prev = (_reach_status().get(url) or (None,))[0]
    ev = record("reach_mark", url=url, status=mark, job=f"{row['company']} - {row['title']}", ats=row["ats"])
    if REACH_STATUS[mark]:
        record("application", job=f"{row['company']} - {row['title']}", url=url, status=REACH_STATUS[mark],
               detail=f"by you on {row['ats']} (reach list)", resume=row["resume"], dry=False, by="user")
    elif prev and prev != "todo":  # undo: the latest application status for this url is no longer final
        record("application", job=f"{row['company']} - {row['title']}", url=url, status="RESET",
               detail=f"your {prev} mark was undone (reach list)", dry=False, by="user")
    return {"ok": True, "url": url, "mark": mark, "ts": ev.get("ts") if isinstance(ev, dict) else None}


@router.get("/control/bench")
def bench():
    """Latest benchmark run B1-B7 (engine/bench.py; the supervisor saves one every REGEN_BENCH_HOURS)."""
    from engine.bench import latest
    return latest() or {"ts": None, "results": {}}


@router.get("/control/evals")
def evals(n: int = 30):
    """Eval history (B1-B10 summaries, oldest first) plus the eval containers the supervisor runs right now."""
    from engine.bench import history
    from engine.supervisor import containers
    snap = containers() or {}
    return {"runs": history(max(1, min(n, 200))),
            "running": [c for c in snap.get("containers", []) if c.get("service") == "eval"]}


@router.post("/control/run")
def run(body: dict, request: Request):
    _guard(request)
    try:
        return C.start(body)
    except RuntimeError as e:
        raise HTTPException(409, str(e))


def _appliers_busy(window=120):
    """True when any applier log was written in the last `window` seconds (a CLI loop or another run is working)."""
    logs = os.path.join(WORKSPACE, "logs")
    now = time.time()
    return any(re.fullmatch(r"run_\d{8}_\d{4}.*\.log", f) and now - os.path.getmtime(os.path.join(logs, f)) < window
               for f in (os.listdir(logs) if os.path.isdir(logs) else []))


@router.post("/control/retry")
def retry(request: Request):
    """Apply again to jobs that are answerable now (pipeline.answerable_now). If appliers are already working, the
    running loop picks them up on its next pass instead (two appliers must not share a browser profile)."""
    if not WRITE and os.environ.get("REGEN_ANSWER_QUEUE") == "1":
        # Docker bank (10-15: "Apply now" hit this 403): the answers container already dropped a retry batch for
        # every saved answer and the supervisor scales appliers to it, so there is nothing to start here.
        if (request.client.host if request.client else "") not in LOCAL and os.environ.get("REGEN_API_TRUST_PORT") != "1":
            raise HTTPException(403, "only from this computer")
        return {"started": False, "note": "Answered jobs are already queued for the appliers (answers container)."}
    _guard(request)
    if C.read_state().get("running") or _appliers_busy():
        return {"started": False, "note": "The engine is already applying; answered jobs join its next pass."}
    s = C.start({"scan": False, "newgrad": False, "feed": False})
    return {"started": True, "note": "Retry pass started.", "run": s}


@router.post("/control/stop")
def stop(request: Request):
    _guard(request)
    return C.stop()


FILTER_KEYS = ("include_titles", "exclude_titles", "exclude_companies")


@router.get("/control/filters")
def filters():
    from engine.discovery.filters import DEFAULT_DOMAIN
    d = dict(DEFAULT_DOMAIN)
    try:
        d.update(json.load(open(profile_file("domains.json"), encoding="utf-8")))
    except (OSError, ValueError):
        pass
    years = None
    try:
        years = json.load(open(profile_file("presets.json"), encoding="utf-8")).get("years_experience")
    except (OSError, ValueError):
        pass
    return {"filters": {k: d.get(k, "") for k in FILTER_KEYS},
            "terms": {k: [t for t in re.split(r"\|", d.get(k, "")) if t] for k in FILTER_KEYS},
            "years_experience": years, "why": d.get("_why", "")}


@router.post("/control/filters")
def set_filters(body: dict, request: Request):
    """Replace title/company filters (regex alternations). Each must compile; the old file is kept as .bak."""
    _guard(request)
    path = profile_file("domains.json")
    try:
        cur = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        cur = {}
    for k in FILTER_KEYS:
        if k in body:
            v = str(body[k])
            try:
                re.compile(v, re.I)
            except re.error as e:
                raise HTTPException(422, f"{k}: {e}")
            cur[k] = v
    if os.path.exists(path):
        shutil.copy(path, path + ".bak-ui")
    json.dump(cur, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return filters()


@router.get("/rules")
def rules():
    """Every rule that drives the engine, grouped by the stage it runs in, with firing counts (engine/rules.py)."""
    from engine.rules import catalog
    return catalog()


@router.get("/factbank")
def factbank():
    """The Fact Bank as the UI draws it: every entry, which resumes used it, in which lanes."""
    try:
        fb = json.load(open(profile_file("fact_bank.json"), encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(404, "no fact bank")
    from engine.feedback.events import read
    used, lanes = collections.defaultdict(list), collections.defaultdict(collections.Counter)
    role_of = {}
    for e in read():
        if e.get("kind") != "resume":
            continue
        for role, fids in e.get("facts") or []:
            for f in fids:
                used[f].append({"job": e.get("job"), "url": e.get("url"), "ts": e.get("ts")})
                lanes[f][e.get("lane") or "?"] += 1
                role_of.setdefault(f, role)
    strip = lambda s: re.sub(r"<[^>]+>", "", s or "")
    facts = [{"id": k, "text": strip(v), "role": role_of.get(k), "uses": len(used[k]), "lanes": dict(lanes[k]),
              "recent": used[k][-5:][::-1]} for k, v in fb.get("facts", {}).items()]
    facts.sort(key=lambda f: -f["uses"])
    return {
        "name": dict(fb.get("contact", {})).get("name"),
        "facts": facts,
        "roles": [{"id": k, "org": v[0], "title": v[1], "where": v[2], "when": v[3]} for k, v in fb.get("roles", {}).items()],
        "projects": [{"id": k, "name": v[0], "when": v[1], "points": [strip(x) for x in v[2]]} for k, v in fb.get("projects", {}).items()],
        "skills": [{"id": k, "label": v[0], "items": [s.strip() for s in v[1].split(",")]} for k, v in fb.get("skills", {}).items()],
        "education": [{"degree": e[0], "when": e[1]} for e in fb.get("education", []) if isinstance(e, list)],
        "awards": fb.get("awards", []), "publications": fb.get("publications", []),
        # a source is {date, file, added}; facts added from chat were logged as one plain line ("<date> <note>")
        "sources": [s if isinstance(s, dict) else {"date": str(s)[:10], "file": str(s)[11:], "added": []}
                    for s in fb.get("_sources", [])],
        "overlaps": fb.get("_overlaps", []),
        "resumes_built": sum(1 for e in read() if e.get("kind") == "resume"),
    }


@router.get("/resume/{name}")
def resume(name: str, download: int = 0):
    """A resume PDF the engine built, by file name only, from workspace/out."""
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+\.pdf", name):
        raise HTTPException(400, "bad name")
    p = os.path.join(WORKSPACE, "out", name)
    if not os.path.exists(p):
        raise HTTPException(404)
    if download:  # the reach page's "Download" button: a file to upload into the portal
        return FileResponse(p, media_type="application/pdf", filename=name)
    origins = " ".join(os.environ.get("REGEN_WEB_ORIGINS", "http://127.0.0.1:3000 http://localhost:3000").replace(",", " ").split())
    return FileResponse(p, media_type="application/pdf", headers={  # framed by the control room's Applications page only
        "Content-Disposition": f'inline; filename="{name}"', "Content-Security-Policy": f"frame-ancestors {origins}"})


@router.get("/outreach")
def outreach():
    """Outreach drafts built by `engine outreach` (workspace/outreach/drafts.json). Nothing here sends mail."""
    path = os.path.join(WORKSPACE, "outreach", "drafts.json")
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return []


@router.post("/outreach/build")
def outreach_build(body: dict, request: Request):
    """Rebuild drafts for submissions in the last `days` days (1-30)."""
    _guard(request)
    from engine import outreach as O
    return O.build(max(1, min(int(body.get("days", 7)), 30)))


# ---------------- gearbox: the engine's speed control + the rejection feedback it is coupled to ----------------
GEAR_WRITE = WRITE or os.environ.get("REGEN_API_GEAR") == "1"  # bank: shifting gears is the only control write


@router.get("/control/gearbox")
def gearbox():
    """Gear, clutch, what they set, the feedback loop's learned rules, and the engine's live speed (submissions/hour)."""
    from engine import gearbox as G
    from engine.feedback.events import read
    from engine.feedback.rejections import load_gate
    gate = load_gate()
    now = time.time()
    subs = [e for e in read("application") if (e.get("status") or "").startswith("SUBMITTED") and not e.get("dry")]

    def per(hours):
        cut = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now - hours * 3600))
        return sum(1 for e in subs if str(e.get("ts", "")) >= cut)
    outs = collections.Counter(o.get("outcome") for o in read("outcome"))
    fleet = {}
    try:
        from engine.supervisor import fleet as F
        f = F()
        fleet = {"appliers_up": sum(1 for m in f.get("members", []) if m.get("role") == "applier" and m.get("up")),
                 "inbox": f.get("inbox"), "claimed": f.get("claimed"), "verdict": f.get("verdict")}
    except Exception:
        pass
    s = G.spec()
    s["appliers"] = list(s["appliers"])
    return {"gear": s, "fleet": fleet, "speed": {"last_hour": per(1), "last_24h": per(24)},
            "outcomes": dict(outs), "feedback": {"updated": gate.get("updated"), "stats": gate.get("stats", {}),
                                                 "rules": gate.get("rules", [])[:20]}}


@router.post("/control/gearbox")
def shift(body: dict, request: Request):
    """Shift gear (N, 1-4) and/or set the clutch (on/off). Needs REGEN_API_GEAR=1 (bank) or REGEN_API_WRITE=1."""
    if not GEAR_WRITE:
        raise HTTPException(403, "gear writes are disabled (REGEN_API_GEAR=1 in the bank, REGEN_API_WRITE=1 locally)")
    if not TRUST_PORT and (request.client.host if request.client else "") not in LOCAL:
        raise HTTPException(403, "only from this computer")
    from engine import gearbox as G
    try:
        G.shift(body.get("gear"), body.get("clutch"), by="control room")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return gearbox()


# ---------------- oil change: the deep clean the supervisor runs when oil life runs low (engine/oilchange.py) -------
@router.get("/control/oilchange")
def oilchange():
    """Oil life, what is contaminating it, the change running now (stage by stage) and the last 20 changes. Reads
    workspace/oilchange.json, which the supervisor rewrites every 5 minutes and after every stage. O(1)."""
    from engine import oilchange as O
    st = O.load()
    now = time.time()
    return {"life": st.get("life"), "wear": st.get("wear") or {}, "contaminants": st.get("contaminants") or {},
            "limits": O.LIMITS, "interval_h": O.INTERVAL_H, "change_at": O.CHANGE_AT, "stages": list(O.STAGES),
            "running": bool(st.get("running")), "stage": st.get("stage"), "run": st.get("run") if st.get("running") else None,
            "last_change": st.get("last_change"), "next_due": st.get("next_due"), "inspected": st.get("inspected"),
            "requested": os.path.exists(O.REQUEST), "history": (st.get("history") or [])[:20], "now": now}


@router.post("/control/oilchange")
def oilchange_now(request: Request):
    """Ask the supervisor to change the oil now (it starts within 15 s). Same write gate as the gearbox."""
    if not GEAR_WRITE:
        raise HTTPException(403, "control writes are disabled (REGEN_API_GEAR=1 in the bank, REGEN_API_WRITE=1 locally)")
    if not TRUST_PORT and (request.client.host if request.client else "") not in LOCAL:
        raise HTTPException(403, "only from this computer")
    from engine import oilchange as O
    O.request("control room")
    return oilchange()


# ---------------- MCP: the cord any AI client drives the engine with (engine/connectors/mcp_server.py) ----------------
MCP_GROUPS = [("discovery", r"discovery|boards_add|feed_add|companies_probe|leads_add|harvest|job_queue|priority"),
              ("fitgate", r"fit_check|feedback_rule|trust_check|filters"), ("gearbox", r"gear|feedback"), ("fleet", r"fleet|kill|scale|audit|quarantine"),
              ("pipeline", r"pipeline|run_|codes|control_state|job_queue|priority"),
              ("answers", r"answer|needs|human|inbox"), ("ledger", r"ledger"), ("repo", r"reposync"),
              ("memory", r".")]


@router.get("/control/mcp")
def mcp_servers():
    """Both MCP servers (stdio on your machine, HTTP in the bank), each tool with its level and whether it writes,
    and a live initialize probe of the bank's HTTP endpoint. O(tools)."""
    import asyncio, urllib.request
    from engine.connectors.mcp_server import mcp, WRITE as MCP_WRITE
    tools = []
    for t in asyncio.run(mcp.list_tools()):
        d = t.description or ""
        group = next(g for g, rx in MCP_GROUPS if re.search(rx, t.name))
        tools.append({"name": t.name, "about": d, "group": group,
                      "writes": "REGEN_MCP_WRITE=1" in d or t.name in ("kill", "answer_queue_add")})
    url = os.environ.get("REGEN_MCP_URL") or ("http://mcp:8790/mcp" if os.environ.get("REGEN_ANSWER_QUEUE") == "1"
                                               else "http://127.0.0.1:8790/mcp")
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "regen-api", "version": "1"}}}).encode()
    probe = {"url": url.replace("mcp:8790", "127.0.0.1:8790"), "up": False}
    t0 = time.time()
    try:
        req = urllib.request.Request(url, body, {"content-type": "application/json", "accept": "application/json, text/event-stream"})
        with urllib.request.urlopen(req, timeout=4) as r:
            probe.update(up=r.status == 200, ms=round((time.time() - t0) * 1000))
    except Exception as e:
        probe["error"] = type(e).__name__
    return {"servers": [{"name": "regen-bank", "transport": "HTTP (bank container)", **probe},
                        {"name": "regen-engine", "transport": "stdio (your AI client starts it)", "up": None}],
            "write_enabled": MCP_WRITE, "tools": tools,
            "groups": dict(collections.Counter(t["group"] for t in tools))}
