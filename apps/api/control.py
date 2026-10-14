"""v0.10 control room API: start/stop runs with filters, watch every stage while it processes, see the Fact Bank,
open any resume that was sent. Reads are local evidence; writes (run, stop, filters) need REGEN_API_WRITE=1 and
a request from this computer, like POST /api/answers.
"""
import collections, json, os, re, shutil, time

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


@router.get("/control/state")
def state():
    """The run (if one was started from the UI), every applier active in the last 15 minutes, queue, limits."""
    s = C.read_state()
    logs = os.path.join(WORKSPACE, "logs")
    now = time.time()
    appliers = []
    if os.path.isdir(logs):
        for f in sorted(os.listdir(logs)):
            p = os.path.join(logs, f)
            if re.fullmatch(r"run_\d{8}_\d{4}(_w?\d+)?[a-z]?_?\d*b?\.log", f) and now - os.path.getmtime(p) < 900:
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
    from engine.discovery.reach import load
    rows = load()
    marks = _reach_status()
    live = [dict(r, mark=(marks.get(r["url"]) or ("todo", None))[0], marked=(marks.get(r["url"]) or (None, None))[1])
            for r in rows if r.get("resume")][::-1]
    by = collections.Counter(r["ats"] for r in live)
    return {"rows": live[:max(1, min(limit, 500))], "listed": len(live), "gated": len(rows) - len(live), "by_ats": dict(by),
            "marks": dict(collections.Counter(r["mark"] for r in live)), "write": REACH_WRITE}


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
