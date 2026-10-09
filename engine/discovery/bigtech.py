"""Big-tech careers sites (Amazon, NVIDIA) -> fit-gated, tailored, ready-to-submit list.

    python -m engine bigtech [days=3]

These employers run their own portals behind a candidate account (sign-in, often 2FA), so the engine does not
submit there: an account is yours to create and use. What it does is the slow part: poll each site's public search
API, keep US roles that pass the same title filter and fit gate as every other job, build the tailored resume, and
write workspace/bigtech.md (link, posted date, lane, JD coverage, resume path) so each one is a two-minute apply.

Calls: Amazon 1 GET per query page (search.json carries the full JD); NVIDIA 1 POST per query + 1 GET per kept job
(Workday's public cxs API). Already-listed jobs are skipped (workspace/bigtech_seen.json), so a re-run fetches
only new postings. O(postings) time, O(kept) space.
"""
import datetime, html, json, os, re, sys, urllib.request

from engine.config import WORKSPACE, in_workspace
from engine.discovery.filters import keep, load_domain
from engine.feedback.events import record

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Content-Type": "application/json"}
AMAZON_Q = ["software development engineer", "software engineer", "machine learning engineer", "data engineer"]
NVIDIA_Q = ["software engineer new college grad", "software engineer", "AI engineer", "systems software engineer"]
NV = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite"


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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    days = int(argv[0]) if argv else 3
    from engine.tailoring.batch import load_lanes, route
    from engine.tailoring.tailor import tailor, fit
    from engine.tailoring import resume
    from engine.tailoring.compose import ats_check
    dom, cfg = load_domain(), load_lanes()
    with in_workspace():
        seen_f = "bigtech_seen.json"
        seen = set(json.load(open(seen_f))) if os.path.exists(seen_f) else set()
        rows, dropped = [], {}
        for src in (amazon, nvidia):
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
                        j["jd"] = _text(_get(j["_detail"]).get("jobPostingInfo", {}).get("jobDescription", ""))
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
