"""Source-first discovery across the open ATS APIs: Greenhouse, Ashby, Lever, Workable, plus (v0.13 "Reach")
SmartRecruiters, Workday and iCIMS.

A posting appears on these public board APIs the moment a recruiter publishes it, hours or days before
LinkedIn/Indeed syndication. Every job is normalized to one record:

  {source, ats, token, id, company, title, location, posted (ISO UTC), url, jd_url}

Boards live in workspace/boards.json  {"greenhouse": [...], "ashby": [...], "lever": [...], ...}

Reach ATSs (REACH): the engine discovers, fit-gates and tailors for them, but does not fill their forms (Workday and
iCIMS put the form behind a candidate account; SmartRecruiters has no filler yet). Their jobs go to the reach list
(engine/discovery/reach.py) for the user to submit. Board tokens:
  smartrecruiters  company identifier            (jobs.smartrecruiters.com/<Company>)
  workday          "<tenant>.wd<N>/<site>"       (<tenant>.wd<N>.myworkdayjobs.com/[locale/]<site>)
  icims            "<subdomain>"                 (<subdomain>.icims.com/jobs)
(seeded from the legacy workspace/boards.txt and grown by `python -m engine boards harvest`).
"""
import json, os, re, time, urllib.request, urllib.error, concurrent.futures as cf
from datetime import datetime, timedelta, timezone

from engine.config import PACKAGE, WORKSPACE

OPEN_ATS = ("greenhouse", "ashby", "lever", "workable")   # board token = a guessable company slug
FILLED = ("rippling",)  # board token is not a guessable slug, but the runner fills the form (no account, no captcha seen)
REACH = ("smartrecruiters", "workday", "icims", "jazzhr")  # discovered + tailored; the user / the desk submits
ATS = OPEN_ATS + FILLED + REACH
SLUGGABLE = OPEN_ATS + ("smartrecruiters",)                 # newgrad/probe may guess these from a company name
APPLY_SUPPORTED = ("greenhouse", "ashby", "rippling")  # the runner fills these; other ATS jobs get a resume + a human click
# 10-15: Rippling dry runs on two real US postings filled every required field and left Apply enabled -> FILLED.
UA = {"User-Agent": "regen-engine/0.4 (+https://github.com/sameernagar-hub/regen-engine)"}


def _get(url, timeout=20, retries=2):
    for i in range(retries + 1):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout))
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return None          # board gone or renamed: not worth retrying
            if i == retries:
                raise
        except Exception:
            if i == retries:
                raise
        time.sleep(1.5 * (i + 1))


def _iso(ts):
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000, timezone.utc).isoformat(timespec="seconds")
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="seconds")


# ---- per-ATS fetchers: token -> list of normalized jobs (description not included) ----
def greenhouse(token):
    d = _get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    if d is None:
        return None
    out = []
    for j in (d or {}).get("jobs", []):
        out.append(dict(ats="greenhouse", token=token, id=str(j["id"]), company=j.get("company_name") or token,
                        title=j["title"], location=(j.get("location") or {}).get("name", ""),
                        posted=_iso(j.get("first_published") or j.get("updated_at")),
                        url=f"https://job-boards.greenhouse.io/{token}/jobs/{j['id']}"))
    return out


def ashby(token):
    d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
    if d is None:
        return None
    out = []
    for j in (d or {}).get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        addr = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry", "")
        loc = " / ".join(x for x in locs if x)
        if addr and addr not in loc:
            loc = f"{loc} ({addr})" if loc else addr
        if j.get("isRemote") and "remote" not in loc.lower():
            loc += " (Remote)"
        out.append(dict(ats="ashby", token=token, id=j["id"], company=token, title=j["title"], location=loc,
                        posted=_iso(j.get("publishedAt")), url=j.get("jobUrl") or f"https://jobs.ashbyhq.com/{token}/{j['id']}"))
    return out


def lever(token):
    d = _get(f"https://api.lever.co/v0/postings/{token}?mode=json")
    if d is None:
        return None
    out = []
    for j in d or []:
        cat = j.get("categories") or {}
        loc = cat.get("location") or ", ".join(cat.get("allLocations") or [])
        if j.get("country") and j["country"] not in loc:
            loc = f"{loc} ({j['country']})"
        out.append(dict(ats="lever", token=token, id=j["id"], company=token, title=j["text"], location=loc,
                        posted=_iso(j.get("createdAt")), url=j.get("hostedUrl")))
    return out


def workable(token):
    d = _get(f"https://apply.workable.com/api/v1/widget/accounts/{token}")
    if d is None:
        return None
    out = []
    for j in d.get("jobs", []):
        locs = j.get("locations") or [{"city": j.get("city"), "region": j.get("state"), "country": j.get("country")}]
        loc = " / ".join(", ".join(x for x in (l.get("city"), l.get("region"), l.get("country")) if x) for l in locs)
        if j.get("telecommuting") and "remote" not in loc.lower():
            loc += " (Remote)"
        out.append(dict(ats="workable", token=token, id=j["shortcode"], company=d.get("name") or token, title=j["title"],
                        location=loc, posted=_iso((j.get("published_on") or j.get("created_at")) + "T00:00:00+00:00"),
                        url=j.get("url") or f"https://apply.workable.com/j/{j['shortcode']}"))
    return out


def _post(url, body, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=dict(UA, **{"Content-Type": "application/json",
                                                                                     "Accept": "application/json"}))
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        if e.code in (404, 410, 422):
            return None
        raise


def _html(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (regen-engine)"})
        return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return None
        raise


def smartrecruiters(token, pages=5):
    """Public Posting API, US postings, newest first (100 per page, at most `pages` pages). O(postings)."""
    out = []
    for p in range(pages):
        d = _get(f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset={100 * p}&country=us")
        if d is None:
            return None if p == 0 else out
        for j in d.get("content", []):
            loc = j.get("location") or {}
            where = loc.get("fullLocation") or ", ".join(x for x in (loc.get("city"), loc.get("region"), "US") if x)
            if loc.get("remote") and "remote" not in where.lower():
                where += " (Remote)"
            out.append(dict(ats="smartrecruiters", token=token, id=str(j["id"]),
                            company=(j.get("company") or {}).get("name") or token, title=j["name"], location=where,
                            posted=_iso(j.get("releasedDate")), url=f"https://jobs.smartrecruiters.com/{token}/{j['id']}"))
        if 100 * (p + 1) >= d.get("totalFound", 0):
            break
    return out


def _wd_days(s):
    """Workday's "Posted Today / Yesterday / 3 Days Ago / 30+ Days Ago" -> days (None when unreadable)."""
    s = (s or "").lower()
    if "today" in s:
        return 0
    if "yesterday" in s:
        return 1
    m = re.search(r"(\d+)\+? days", s)
    return int(m.group(1)) if m else None


def _wd_split(token):
    host, site = token.split("/", 1)
    return f"https://{host}.myworkdayjobs.com", host.split(".")[0], site


def _wd_where(j):
    """Location text; "3 Locations" falls back to the first location in the posting path ("/job/US-CA-Irvine/...")."""
    t = (j.get("locationsText") or "").strip()
    if re.fullmatch(r"\d+ Locations?", t):
        seg = ((j.get("externalPath") or "").split("/") + ["", "", ""])[2]
        t = re.sub(r"\s+", " ", seg.replace("---", ", ").replace("-", " ")).strip() + f" (+{t.split()[0]} locations)"
    return t


def workday(token, pages=8, days=7):
    """Workday's public cxs search API (the JSON the careers page itself calls): 20 postings per POST, newest first;
    stops at the first page that reaches postings older than `days`. At most `pages` calls per board."""
    base, tenant, site = _wd_split(token)
    api = f"{base}/wday/cxs/{tenant}/{site}/jobs"
    now, out = datetime.now(timezone.utc), []
    for p in range(pages):
        d = _post(api, {"appliedFacets": {}, "limit": 20, "offset": 20 * p, "searchText": ""})
        if d is None:
            return None if p == 0 else out
        rows = d.get("jobPostings") or []
        old = False
        for j in rows:
            n = _wd_days(j.get("postedOn"))
            if n is None or n > days:
                old = True
                continue
            path = j.get("externalPath") or ""
            jid = path.rsplit("_", 1)[-1] if "_" in path else path.rsplit("/", 1)[-1]
            # unique part first: batch.build names files Resume_<company>_<id[:12]>
            out.append(dict(ats="workday", token=token, id=f"{jid}_{tenant}", company=tenant, title=j["title"],
                            location=_wd_where(j), posted=(now - timedelta(days=n)).isoformat(timespec="seconds"),
                            url=f"{base}/en-US/{site}{path}", path=path))
        if old or len(rows) < 20:
            break
    return out


def _icims_where(t):
    """iCIMS "US-VA-Norfolk" -> "Norfolk, VA, US" (so the US-location filter reads it)."""
    m = re.fullmatch(r"([A-Z]{2})-([A-Z]{2})-(.+)", (t or "").strip())
    return f"{m.group(3)}, {m.group(2)}, {m.group(1)}" if m else (t or "").strip()


ICIMS_SEEN = os.path.join(WORKSPACE, "icims_seen.json")
ICIMS_CARD = re.compile(r'href="(https://[^"]+/jobs/(\d+)/[^"?]*/job)[^"]*"[^>]*>.*?<h3[^>]*>\s*(.*?)\s*</h3>(.*?)(?=<li class="iCIMS_JobCardItem"|</ul>)', re.S)
ICIMS_LOC = re.compile(r"Location[^<]*</span>\s*</dt>\s*<dd[^>]*>\s*<span[^>]*>\s*([^<]+?)\s*</span>", re.S)


def icims(token, pages=5, _seen=None):
    """iCIMS career portal search pages (HTML; no public JSON). The list shows no posted date, so `posted` is when
    the engine first saw the job: the first fetch of a board marks everything already open as old (no flood), later
    fetches date new ids to that pass. The job page's JSON-LD (read in job_description) has the JD.
    At most `pages` GETs per board."""
    seen = _seen if _seen is not None else _load_json(ICIMS_SEEN)
    first = token not in seen
    mine = seen.setdefault(token, {})
    out, now = [], datetime.now(timezone.utc).isoformat(timespec="seconds")
    for p in range(pages):
        page = _html(f"https://{token}.icims.com/jobs/search?ss=1&in_iframe=1&pr={p}")
        if page is None:
            return None if p == 0 else out
        cards = ICIMS_CARD.findall(page)
        if not cards:
            break
        for url, jid, title, rest in cards:
            loc = ICIMS_LOC.search(rest)
            mine.setdefault(jid, "2000-01-01T00:00:00+00:00" if first else now)
            out.append(dict(ats="icims", token=token, id=f"{jid}_{token}", company=re.sub(r"^(careers|jobs|uscareers)-", "", token),
                            title=re.sub(r"\s+", " ", title), location=_icims_where(loc.group(1) if loc else ""),
                            posted=mine[jid], url=url))
        if f"pr={p + 1}" not in page:
            break
    if _seen is None:
        _save_json(ICIMS_SEEN, seen)
    return out


RIPPLING_SEEN = os.path.join(WORKSPACE, "rippling_seen.json")


def rippling(token, _seen=None):
    """Rippling ATS public board JSON (api.rippling.com/platform/api/ats/v1/board/<slug>/jobs). The list has no
    posted date (the job detail has createdOn, read in job_description), so `posted` is first-seen like iCIMS: the
    first fetch of a board marks what is already open as old. One GET per board."""
    d = _get(f"https://api.rippling.com/platform/api/ats/v1/board/{token}/jobs")
    if d is None:
        return None
    seen = _seen if _seen is not None else _load_json(RIPPLING_SEEN)
    first = token not in seen
    mine = seen.setdefault(token, {})
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = []
    for j in d if isinstance(d, list) else []:
        mine.setdefault(j["uuid"], "2000-01-01T00:00:00+00:00" if first else now)
        out.append(dict(ats="rippling", token=token, id=j["uuid"], company=re.sub(r"-careers?$", "", token),
                        title=(j.get("name") or "").strip(), location=(j.get("workLocation") or {}).get("label", ""),
                        posted=mine[j["uuid"]], url=j.get("url") or f"https://ats.rippling.com/{token}/jobs/{j['uuid']}"))
    if _seen is None:
        _save_json(RIPPLING_SEEN, seen)
    return out


JAZZ_ROW = re.compile(r'<tr id="row_job_(\d{14})_[A-Z0-9]+"[^>]*>\s*<td>\s*<a class="job_title_link" href="/apply/jobs/details/'
                      r'([A-Za-z0-9]+)[^"]*">([^<]+)</a>.*?</td>\s*<td>\s*([^<]*?)\s*</td>', re.S)


def jazzhr(token):
    """JazzHR (<co>.applytojob.com/apply/jobs) listing HTML. Each row id carries the job's creation time
    (row_job_YYYYMMDDhhmmss_...), so `posted` is real. One GET per board."""
    import html as H
    page = _html(f"https://{token}.applytojob.com/apply/jobs")
    if page is None:
        return None
    out = []
    for stamp, jid, title, where in JAZZ_ROW.findall(page):
        posted = datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()
        out.append(dict(ats="jazzhr", token=token, id=jid, company=token, title=H.unescape(title).strip(),
                        location=H.unescape(where).strip(), posted=posted,
                        url=f"https://{token}.applytojob.com/apply/{jid}"))
    return out


def _load_json(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + f".{os.getpid()}.tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, path)


FETCH = {"greenhouse": greenhouse, "ashby": ashby, "lever": lever, "workable": workable,
         "smartrecruiters": smartrecruiters, "workday": workday, "icims": icims, "rippling": rippling, "jazzhr": jazzhr}


def yc_job(url):
    """Props of a ycombinator.com job page (Inertia data-page JSON): job (description, visa), company,
    showDirectApply (the page's own no-account "Apply to <company>" form is there) and customQuestions."""
    import html as H
    m = re.search(r'data-page="([^"]*)"', _html(url) or "")
    try:
        return json.loads(H.unescape(m.group(1))).get("props") if m else None
    except ValueError:
        return None


def job_description(job):
    """(raw json, plain-text JD, greenhouse questions or []) for one normalized job."""
    import html as H
    clean = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", H.unescape(s or ""))).strip()
    if job["ats"] == "greenhouse":
        d = _get(f"https://boards-api.greenhouse.io/v1/boards/{job['token']}/jobs/{job['id']}?questions=true")
        return d, clean((d or {}).get("content")), (d or {}).get("questions", [])
    if job["ats"] == "ashby":
        d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{job['token']}")
        j = next((x for x in (d or {}).get("jobs", []) if x["id"] == job["id"]), None)
        return j, (j or {}).get("descriptionPlain") or clean((j or {}).get("descriptionHtml")), []
    if job["ats"] == "workable":
        d = _get(f"https://apply.workable.com/api/v2/accounts/{job['token']}/jobs/{job['id']}")
        if not d:
            return None, "", []
        return d, clean(" ".join(str(d.get(k) or "") for k in ("description", "requirements", "benefits"))), []
    if job["ats"] == "lever":
        d = _get(f"https://api.lever.co/v0/postings/{job['token']}/{job['id']}?mode=json")
        if not d:
            return None, "", []
        lists = " ".join(f"{x.get('text', '')}: {clean(x.get('content'))}" for x in d.get("lists", []))
        return d, " ".join([d.get("descriptionPlain") or "", lists, d.get("additionalPlain") or ""]), []
    if job["ats"] == "smartrecruiters":
        d = _get(f"https://api.smartrecruiters.com/v1/companies/{job['token']}/postings/{job['id']}")
        if not d:
            return None, "", []
        secs = (d.get("jobAd") or {}).get("sections") or {}
        return d, clean(" ".join((secs.get(k) or {}).get("text", "") for k in
                                 ("companyDescription", "jobDescription", "qualifications", "additionalInformation"))), []
    if job["ats"] == "workday":
        base, tenant, site = _wd_split(job["token"])
        d = _get(f"{base}/wday/cxs/{tenant}/{site}{job.get('path') or ''}")
        return d, clean(((d or {}).get("jobPostingInfo") or {}).get("jobDescription")), []
    if job["ats"] == "icims":
        page = _html(job["url"] + "?in_iframe=1")
        for blob in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page or "", re.S):
            try:
                d = json.loads(blob)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("@type") == "JobPosting":
                return d, clean(d.get("description")), []
        return None, "", []
    if job["ats"] == "rippling":
        d = _get(f"https://api.rippling.com/platform/api/ats/v1/board/{job['token']}/jobs/{job['id']}")
        desc = (d or {}).get("description") or {}
        text = " ".join(str(v) for v in desc.values()) if isinstance(desc, dict) else str(desc)
        return d, clean(text), []
    if job["ats"] == "yc":
        d = yc_job(job["url"])
        if not d:
            return None, "", []
        j = d.get("job") or {}
        qs = [{"label": q.get("question") or q.get("label") or str(q), "required": bool(q.get("required"))}
              for q in d.get("customQuestions") or [] if isinstance(q, dict)]
        return d, clean(" ".join([j.get("description") or "", f"Visa: {j.get('visa') or ''}."])), qs
    if job["ats"] == "jazzhr":
        page = _html(f"https://{job['token']}.applytojob.com/apply/jobs/details/{job['id']}")
        for blob in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page or "", re.S):
            try:
                d = json.loads(blob)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("@type") == "JobPosting":
                return d, clean(d.get("description")), []
        return None, "", []
    return None, "", []


# ---- board registry ----
def boards_path():
    return os.path.join(WORKSPACE, "boards.json")


def load_boards():
    path = boards_path()
    if os.path.exists(path):
        b = json.load(open(path))
    else:
        b = {a: [] for a in ATS}
        legacy = os.path.join(WORKSPACE, "boards.txt")
        src = legacy if os.path.exists(legacy) else os.path.join(PACKAGE, "discovery", "boards.example.txt")
        b["greenhouse"] = [t.strip() for t in open(src).read().replace("\n", ",").split(",") if t.strip()]
    for a in ATS:
        b.setdefault(a, [])
    return b


def save_boards(b):
    os.makedirs(WORKSPACE, exist_ok=True)
    json.dump({a: sorted(set(b.get(a, [])), key=str.lower) for a in ATS} | {k: v for k, v in b.items() if k not in ATS},
              open(boards_path(), "w"), indent=1)


def fetch_all(boards, workers=24, keep=None, keys=None, activity=None, only=None):
    """Fetch every board in parallel and stream each one through `keep` as it arrives.

    keep(job) -> bool   only kept jobs are held in memory (default: keep all)
    keys: set | None    if given, every "ats:id" seen is added to it (cheap strings, for watch's seen-set)
    activity: dict|None if given, "ats:token" -> postings first published in the last 7 days (board ranking)
    only: set | None    "ats:token" boards to fetch (scan --hot); None = every live board
    Returns (kept jobs, dead boards, total postings). Boards that 404 are reported as dead; boards that fail
    with a network error are kept and retried on the next pass. Streaming keeps a full pass of ~110k postings
    at a fraction of the memory of holding them all."""
    dead_known = set(boards.get("dead", []))  # skipped to save calls (`boards recheck` retries them)
    tasks = [(a, t) for a in ATS for t in boards.get(a, [])
             if f"{a}:{t}" not in dead_known and (only is None or f"{a}:{t}" in only)]
    week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    kept, dead, total = [], [], 0

    def one(at):
        try:
            r = FETCH[at[0]](at[1])
        except Exception:
            return at, [], [], 0                      # transient: keep the board
        if r is None:
            return at, None, [], 0
        ids = [f"{j['ats']}:{j['id']}" for j in r] if keys is not None else []
        if activity is not None:
            activity[f"{at[0]}:{at[1]}"] = sum(1 for j in r if (j.get("posted") or "") >= week)
        return at, ([j for j in r if keep(j)] if keep else r), ids, len(r)

    with cf.ThreadPoolExecutor(workers) as ex:
        for fut in cf.as_completed([ex.submit(one, at) for at in tasks]):
            at, r, ids, n = fut.result()
            if r is None:
                dead.append(at)
                continue
            kept += r; total += n
            if keys is not None:
                keys.update(ids)
    return kept, dead, total


HARVEST = {
    "greenhouse": r"greenhouse\.io/(?:embed/job_app\?for=)?([A-Za-z0-9_-]+)",
    "ashby": r"jobs\.ashbyhq\.com/([^/?#]+)",
    "lever": r"jobs\.lever\.co/([^/?#]+)",
    "workable": r"apply\.workable\.com/(?!j/|api/)([^/?#]+)",
    "smartrecruiters": r"(?:jobs|careers)\.smartrecruiters\.com/(?!oneclick|sr-jobs|api)([A-Za-z0-9_-]+)",
    "workday": r"([a-z0-9-]+\.wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)",
    "icims": r"//((?:careers|jobs|uscareers)-[a-z0-9-]+)\.icims\.com",
    "rippling": r"ats\.rippling\.com/(?!api)([A-Za-z0-9-]+)",
    "jazzhr": r"//([a-z0-9-]+)\.applytojob\.com",
}
HARVEST_FEEDS = [  # machine-readable lists (JSON with "url") and READMEs (any ATS link in the markdown)
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json",
    "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/README.md",
    "https://raw.githubusercontent.com/vanshb03/New-Grad-2026/main/README.md",
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/master/README.md",
    "https://raw.githubusercontent.com/ReaVNaiL/New-Grad-2024/main/README.md",
    # 10-10: more lists. Intern and older lists still name each company's board, and a board lists every open role
    # (new grad and experienced), so they widen the pool; a missing list is skipped.
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/.github/scripts/listings.json",
    "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/NEW_GRAD_USA.md",
    "https://raw.githubusercontent.com/speedyapply/2026-AI-College-Jobs/main/README.md",
    "https://raw.githubusercontent.com/jobright-ai/2026-Software-Engineer-New-Grad/master/README.md",
    "https://raw.githubusercontent.com/cvrve/New-Grad-2026/main/README.md",
    "https://raw.githubusercontent.com/Ouckah/Summer2026-Internships/main/README.md",
    "https://raw.githubusercontent.com/vanshb03/Summer2026-Internships/main/README.md",
    "https://raw.githubusercontent.com/poteto/hiring-without-whiteboards/main/README.md",
    "https://raw.githubusercontent.com/remoteintech/remote-jobs/main/README.md",
    # 10-11: the 2027 cycle lists (probed 200 OK); each new board lists every open role, not only campus ones
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json",
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md",
    "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/README.md",
    "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/NEW_GRAD_USA.md",
    "https://raw.githubusercontent.com/speedyapply/2027-AI-College-Jobs/main/README.md",
    "https://raw.githubusercontent.com/vanshb03/New-Grad-2027/main/README.md",
    "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/main/README.md",
    "https://raw.githubusercontent.com/zapplyjobs/New-Grad-Jobs/main/README.md",
    "https://raw.githubusercontent.com/codicate/underclassmen-internships/main/README.md",
    "https://raw.githubusercontent.com/northwesternfintech/2027QuantInternships/main/README.md",
    # 10-17: probed 200 OK. Older and non-SWE lists still name company boards that list every open role
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2024-Internships/dev/.github/scripts/listings.json",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md",
    "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/INTERN_INTL.md",
    "https://raw.githubusercontent.com/jobright-ai/2026-Software-Engineer-Internship/master/README.md",
    "https://raw.githubusercontent.com/jobright-ai/2026-Data-Analysis-New-Grad/master/README.md",
    "https://raw.githubusercontent.com/jobright-ai/2026-Product-Management-New-Grad/master/README.md",
    "https://raw.githubusercontent.com/pittcsc/Summer2024-Internships/dev/README.md",
]


def harvest_urls(urls):
    """Board tokens found in a list of job URLs, per ATS."""
    found = {a: set() for a in ATS}
    for u in urls:
        for a, pat in HARVEST.items():
            m = re.search(pat, u or "")
            if not m or m.group(1).lower() in ("embed", "v1", "jobs", "job_app"):
                continue
            if a == "workday":
                if m.group(2).lower() not in ("job", "wday", "details"):
                    found[a].add(f"{m.group(1).lower()}/{m.group(2)}")
            else:
                found[a].add(m.group(1) if a in ("ashby", "smartrecruiters") else m.group(1).lower())
    return found


def harvest(feeds=None):
    """Grow boards.json with every ATS board referenced by the public GitHub job lists (+ feeds added over MCP)."""
    if feeds is None:
        from engine.discovery.sources import feeds as all_feeds
        feeds = all_feeds()
    b = load_boards()
    before = {a: len(set(b[a])) for a in ATS}
    urls = []
    for f in feeds:
        try:
            if f.endswith(".json"):
                urls += [x.get("url", "") for x in _get(f, timeout=60) or []]
            else:
                text = urllib.request.urlopen(urllib.request.Request(f, headers=UA), timeout=60).read().decode("utf-8", "replace")
                urls += re.findall(r"https?://[^\s)\]\"'<>]+", text)
        except Exception as e:
            print("  ! harvest", f, e)
    for name in ("leads.json", "alert_leads.json"):  # unresolved leads often point at Workday / iCIMS boards (local, no calls)
        try:
            urls += re.findall(r"https?://[^\s\"'<>]+", open(os.path.join(WORKSPACE, name), encoding="utf-8").read())
        except OSError:
            pass
    for a, toks in harvest_urls(urls).items():
        b[a] = list(set(b[a]) | toks)
    save_boards(b)
    return {a: (before[a], len(set(b[a]))) for a in ATS}
