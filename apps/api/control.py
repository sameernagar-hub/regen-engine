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
WRITE = os.environ.get("REGEN_API_WRITE") == "1"
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
        "sources": fb.get("_sources", []), "overlaps": fb.get("_overlaps", []),
        "resumes_built": sum(1 for e in read() if e.get("kind") == "resume"),
    }


@router.get("/resume/{name}")
def resume(name: str):
    """A resume PDF the engine built, by file name only, from workspace/out."""
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+\.pdf", name):
        raise HTTPException(400, "bad name")
    p = os.path.join(WORKSPACE, "out", name)
    if not os.path.exists(p):
        raise HTTPException(404)
    return FileResponse(p, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'})
