"""Source-first discovery across the three open ATS APIs: Greenhouse, Ashby and Lever.

A posting appears on these public board APIs the moment a recruiter publishes it, hours or days before
LinkedIn/Indeed syndication. Every job is normalized to one record:

  {source, ats, token, id, company, title, location, posted (ISO UTC), url, jd_url}

Boards live in workspace/boards.json  {"greenhouse": [...], "ashby": [...], "lever": [...]}
(seeded from the legacy workspace/boards.txt and grown by `python -m engine boards harvest`).
"""
import json, os, re, time, urllib.request, urllib.error, concurrent.futures as cf
from datetime import datetime, timezone

from engine.config import PACKAGE, WORKSPACE

ATS = ("greenhouse", "ashby", "lever", "workable")
APPLY_SUPPORTED = ("greenhouse", "ashby")  # the runner fills these; other ATS jobs get a resume + a human click
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


FETCH = {"greenhouse": greenhouse, "ashby": ashby, "lever": lever, "workable": workable}


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


def fetch_all(boards, workers=32):
    """Fetch every board in parallel. Returns (jobs, dead) where dead lists (ats, token) boards that 404.
    Boards that fail with a network error are kept and simply retried on the next scan."""
    dead = set(boards.get("dead", []))  # boards that 404'd: skipped to save calls (`boards recheck` retries them)
    tasks = [(a, t) for a in ATS for t in boards.get(a, []) if f"{a}:{t}" not in dead]
    jobs, dead = [], []

    def one(at):
        try:
            return at, FETCH[at[0]](at[1]), None
        except Exception as e:
            return at, [], e

    with cf.ThreadPoolExecutor(workers) as ex:
        for at, r, err in ex.map(one, tasks):
            if r is None:
                dead.append(at)
            else:
                jobs += r
    return jobs, dead


HARVEST = {
    "greenhouse": r"greenhouse\.io/(?:embed/job_app\?for=)?([A-Za-z0-9_-]+)",
    "ashby": r"jobs\.ashbyhq\.com/([^/?#]+)",
    "lever": r"jobs\.lever\.co/([^/?#]+)",
    "workable": r"apply\.workable\.com/(?!j/|api/)([^/?#]+)",
}
HARVEST_FEEDS = [  # machine-readable lists (JSON with "url") and READMEs (any ATS link in the markdown)
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json",
    "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/README.md",
    "https://raw.githubusercontent.com/vanshb03/New-Grad-2026/main/README.md",
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/master/README.md",
    "https://raw.githubusercontent.com/ReaVNaiL/New-Grad-2024/main/README.md",
]


def harvest_urls(urls):
    """Board tokens found in a list of job URLs, per ATS."""
    found = {a: set() for a in ATS}
    for u in urls:
        for a, pat in HARVEST.items():
            m = re.search(pat, u or "")
            if m and m.group(1).lower() not in ("embed", "v1", "jobs", "job_app"):
                found[a].add(m.group(1) if a == "ashby" else m.group(1).lower())
    return found


def harvest(feeds=HARVEST_FEEDS):
    """Grow boards.json with every ATS board referenced by the public GitHub job lists."""
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
    for a, toks in harvest_urls(urls).items():
        b[a] = list(set(b[a]) | toks)
    save_boards(b)
    return {a: (before[a], len(set(b[a]))) for a in ATS}
