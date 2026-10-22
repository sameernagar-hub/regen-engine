"""Big-tech careers sites (Amazon, NVIDIA, Google, Apple, Microsoft, Netflix) -> fit-gated, tailored, ready-to-submit list.

    python -m engine bigtech [days=3] [--force]

The pipeline runs it on its sources passes, at most once per BIG_EVERY_MIN (60) minutes so these sites see a few dozen
polite requests an hour; --force ignores the interval. Every site is also asked for new-grad / early-career roles.

These employers run their own portals behind a candidate account (sign-in, often 2FA), so the engine does not
submit there: an account is yours to create and use. What it does is the slow part: poll each site's public search
API, keep US roles that pass the same title filter and fit gate as every other job, build the tailored resume, and
write workspace/bigtech.md (link, posted date, lane, JD coverage, resume path) so each one is a two-minute apply.

Calls: Amazon 1 GET per query page (search.json carries the full JD); NVIDIA 1 POST per query + 1 GET per kept job
(Workday's public cxs API); Google 1 GET per query (the results page embeds its job list, JD included, as JSON);
Apple 1 GET for a CSRF token + 1 POST per query (summary as JD); Microsoft and Netflix 1 GET per query + 1 GET per
kept job (Eightfold's apply/v2 API). Already-listed jobs are skipped (workspace/bigtech_seen.json), so a re-run
fetches only new postings. O(postings) time, O(kept) space.
"""
import datetime, html, http.cookiejar, json, os, re, sys, time, urllib.error, urllib.request

from engine.config import WORKSPACE, in_workspace
from engine.discovery.filters import keep, load_domain
from engine.feedback.events import record

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Content-Type": "application/json"}
AMAZON_Q = ["software development engineer", "software engineer", "machine learning engineer", "data engineer",
            "new grad", "university graduate", "data scientist", "support engineer"]
NVIDIA_Q = ["software engineer new college grad", "software engineer", "AI engineer", "systems software engineer",
            "new college grad", "data scientist"]
# 10-21: the same search words on every other site, new grad / early career included (user: "new grad in all of them")
BIG_Q = ["software engineer", "new grad", "university graduate", "early career", "entry level", "machine learning engineer",
         "data scientist", "data analyst", "research engineer", "solutions engineer", "support engineer", "test engineer"]
NV = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite"
BIG_EVERY_MIN = float(os.environ.get("REGEN_BIGTECH_EVERY_MIN", "60"))
PAUSE = 1.0  # seconds between requests to one site: a slow, steady client (Microsoft answered 429 to a burst)


def _get(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=25))


def _text(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


def amazon(days):
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    for q in AMAZON_Q:
        url = ("https://www.amazon.jobs/en/search.json?country=USA&sort=recent&result_limit=100&offset=0&base_query="
               + urllib.request.quote(q))
        for j in _get(url).get("jobs", []):
            try:
                posted = datetime.datetime.strptime(" ".join(j["posted_date"].split()), "%B %d, %Y").date()
            except (KeyError, ValueError):
                continue
            if posted < cutoff:
                continue
            jd = _text(" ".join([j.get("description", ""), j.get("basic_qualifications", ""), j.get("preferred_qualifications", "")]))
            yield {"company": "Amazon", "title": j["title"], "location": j.get("normalized_location") or j.get("location", ""),
                   "url": "https://www.amazon.jobs" + j["job_path"], "posted": str(posted), "jd": jd, "id": "amzn_" + str(j["id_icims"])}


def _nv_days(s):
    s = (s or "").lower()
    if "today" in s:
        return 0
    if "yesterday" in s:
        return 1
    m = re.search(r"(\d+)\+? days", s)
    return int(m.group(1)) if m else 99


def nvidia(days):
    for q in NVIDIA_Q:
        res = _get(NV + "/jobs", {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": q})
        for j in res.get("jobPostings", []):
            if _nv_days(j.get("postedOn")) > days or not j.get("externalPath", "").startswith("/job/US-"):
                continue
            yield {"company": "NVIDIA", "title": j["title"], "location": j.get("locationsText", ""), "posted": j.get("postedOn"),
                   "url": "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite" + j["externalPath"],
                   "_detail": NV + j["externalPath"], "id": "nvda_" + j["externalPath"].rsplit("_", 1)[-1]}


def _old(ts, days):
    """True when a unix timestamp is older than `days`."""
    try:
        return datetime.date.fromtimestamp(float(ts)) < datetime.date.today() - datetime.timedelta(days=days)
    except (TypeError, ValueError, OSError):
        return False


def google(days):
    """The results page carries its jobs in AF_initDataCallback ds:1: [id, title, apply url, [_, responsibilities],
    [_, qualifications], ..., [locations], [_, about], _, [created s, ns], ..., [_, sponsorship note]]."""
    for q in BIG_Q:
        url = ("https://www.google.com/about/careers/applications/jobs/results?location=United%20States&sort_by=date&q="
               + urllib.request.quote(q))
        page = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]}), timeout=25).read().decode("utf-8", "replace")
        time.sleep(PAUSE)
        i = page.find("AF_initDataCallback({key: 'ds:1'")
        if i < 0:
            continue
        s = page[i:]
        s = s[s.find("data:") + 5:]
        for j in (json.loads(s[:s.find(", sideChannel")]) or [[]])[0] or []:
            try:
                if _old(j[12][0], days):
                    continue
                part = lambda k: (j[k] or [None, ""])[1] or "" if len(j) > k else ""
                yield {"company": "Google", "title": j[1], "location": "; ".join(l[0] for l in j[9] or []),
                       "url": f"https://www.google.com/about/careers/applications/jobs/results/{j[0]}",
                       "posted": str(datetime.date.fromtimestamp(j[12][0])), "id": f"goog_{j[0]}",
                       "jd": _text(" ".join([part(10), part(3), part(4), part(19), part(15)]))}
            except (IndexError, TypeError, ValueError):
                continue


def apple(days):
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    tok = op.open(urllib.request.Request("https://jobs.apple.com/api/v1/CSRFToken", headers=UA), timeout=20).headers.get("x-apple-csrf-token")
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    for q in BIG_Q:
        body = {"query": q, "filters": {"locations": ["postLocation-USA"]}, "page": 1, "locale": "en-us", "sort": "newest",
                "format": {"longDate": "MMMM D, YYYY", "mediumDate": "MMM D, YYYY"}}  # without "format" it returns 0 rows
        req = urllib.request.Request("https://jobs.apple.com/api/v1/search", data=json.dumps(body).encode(),
                                     headers={**UA, "x-apple-csrf-token": tok or ""})
        rows = json.load(op.open(req, timeout=25)).get("res", {}).get("searchResults", [])
        time.sleep(PAUSE)
        for j in rows:
            try:
                if datetime.datetime.fromisoformat(j["postDateInGMT"].replace("Z", "+00:00")) < cutoff:
                    continue
            except (KeyError, ValueError):
                continue
            locs = "; ".join(", ".join(x for x in (l.get("city"), l.get("stateProvince"), l.get("countryName")) if x)
                             for l in j.get("locations") or [])
            yield {"company": "Apple", "title": j["postingTitle"], "location": locs or "United States",
                   "url": f"https://jobs.apple.com/en-us/details/{j['positionId']}/{j.get('transformedPostingTitle', '')}",
                   "posted": j["postDateInGMT"][:10], "id": f"aapl_{j['positionId']}", "jd": _text(j.get("jobSummary", ""))}


def eightfold(company, host, domain, prefix, pcsx=False):
    """Eightfold career sites (Microsoft, Netflix): a list call per query, the full JD from apply/v2/jobs/<id>.
    pcsx: Microsoft answers 403 to the apply/v2 list (10-21) but serves the same rows from api/pcsx/search
    (`data.positions`, `postedTs` instead of `t_create`)."""
    def run(days):
        for q in BIG_Q:
            url = (f"https://{host}/api/pcsx/search?domain={domain}&location=United%20States&start=0&query=" if pcsx else
                   f"https://{host}/api/apply/v2/jobs?domain={domain}&location=United%20States&sort_by=new&num=50&query=")
            try:
                res = _get(url + urllib.request.quote(q))
            except urllib.error.HTTPError as e:
                if e.code == 429:  # rate limited: keep what this site gave so far, try again next run
                    print(f"  ! {company}: 429 after {BIG_Q.index(q)} queries; rest next run")
                    return
                raise
            time.sleep(PAUSE * (5 if pcsx else 1))  # Microsoft limits bursts (429 at 1 s spacing, 10-21)
            for j in (res.get("data") or {}).get("positions", []) if pcsx else res.get("positions", []):
                ts = j.get("t_create") or j.get("postedTs")
                if _old(ts, days):
                    continue
                yield {"company": company, "title": j["name"], "location": "; ".join(j.get("locations") or [j.get("location", "")]),
                       "url": j.get("canonicalPositionUrl") or f"https://{host}/careers/job/{j['id']}",
                       "posted": str(datetime.date.fromtimestamp(float(ts or 0))), "id": f"{prefix}_{j['id']}",
                       "_detail": f"https://{host}/api/apply/v2/jobs/{j['id']}?domain={domain}", "_jd_key": "job_description"}
    run.__name__ = company.lower()
    return run


microsoft = eightfold("Microsoft", "apply.careers.microsoft.com", "microsoft.com", "msft", pcsx=True)
netflix = eightfold("Netflix", "explore.jobs.netflix.net", "netflix.com", "nflx")
SOURCES = (amazon, nvidia, google, apple, microsoft, netflix)


def due(path="bigtech_last", now=None):
    """True when the last full run is older than BIG_EVERY_MIN minutes (relative to the workspace)."""
    try:
        return (now or time.time()) - os.path.getmtime(path) >= BIG_EVERY_MIN * 60
    except OSError:
        return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    force = "--force" in argv
    argv = [a for a in argv if a != "--force"]
    days = int(argv[0]) if argv else 3
    with in_workspace():
        if not force and not due():
            print(f"bigtech: ran less than {BIG_EVERY_MIN:.0f} min ago; skipped (--force to run now)")
            return
        open("bigtech_last", "w").write(datetime.datetime.now().isoformat())
    from engine.tailoring.batch import load_lanes, route
    from engine.tailoring.tailor import tailor, fit
    from engine.tailoring import resume
    from engine.tailoring.compose import ats_check
    dom, cfg = load_domain(), load_lanes()
    with in_workspace():
        seen_f = "bigtech_seen.json"
        seen = set(json.load(open(seen_f))) if os.path.exists(seen_f) else set()
        rows, dropped = [], {}
        for src in SOURCES:
            try:
                jobs = list(src(days))
            except Exception as e:  # one site down never stops the other
                print(f"  ! {src.__name__}: {e}"); continue
            for j in {j["id"]: j for j in jobs}.values():
                if j["id"] in seen:
                    continue
                why = keep(dom, j["title"], j["location"], j["company"])
                if why:
                    dropped[why] = dropped.get(why, 0) + 1; continue
                if "_detail" in j:
                    try:
                        d = _get(j["_detail"])
                        j["jd"] = _text(d.get(j["_jd_key"], "") if "_jd_key" in j else d.get("jobPostingInfo", {}).get("jobDescription", ""))
                        time.sleep(PAUSE)
                    except Exception:
                        continue
                blockers = fit(j["jd"])
                seen.add(j["id"])
                if blockers:
                    print(f"  x {j['company']} - {j['title']}: {blockers}"); continue
                ln = route(cfg, j["title"], j["jd"])
                spec = tailor(cfg["lanes"][ln], j["jd"], title=j["title"], lanes=cfg["lanes"])
                cov = spec.pop("_coverage")
                spec["file"] = f"Resume_{j['company']}_{j['id'].split('_')[1][:12]}.pdf"
                try:
                    pdf = resume.fit(spec)
                except SystemExit as e:
                    print(f"  x {j['title']}: resume: {e}"); continue
                cov["ats"] = ats_check(pdf, set(cov["jd_terms_you_have"]))
                record("resume", job=f"{j['company']} - {j['title']}", url=j["url"], lane=ln, file=spec["file"],
                       facts=spec["roles"], projects=spec.get("projects", []), skills=spec["skills"], coverage=cov)
                rows.append((j, ln, cov, os.path.relpath(pdf, WORKSPACE)))
                print(f"{j['company']} - {j['title']} | {j['location']} | lane={ln} | ATS {cov['ats']['score']}%")
        json.dump(sorted(seen), open(seen_f, "w"))
        old = open("bigtech.md", encoding="utf-8").read().split("\n", 4)[-1] if os.path.exists("bigtech.md") else ""
        new = "".join(f"| {j['posted']} | {j['company']} | [{j['title']}]({j['url']}) | {j['location'][:40]} | {ln} | "
                      f"{c['ats']['score']}% | `{p}` |\n" for j, ln, c, p in rows)
        open("bigtech.md", "w", encoding="utf-8").write(
            "# Big-tech roles, resume ready (apply on their portal, signed in)\n\n"
            "| Posted | Company | Role | Location | Lane | ATS | Resume |\n|---|---|---|---|---|---|---|\n" + new + old)
    print(f"{len(rows)} new big-tech roles -> workspace/bigtech.md; dropped {dropped}")


if __name__ == "__main__":
    main()
