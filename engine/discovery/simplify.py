"""GitHub list firehose: the SimplifyJobs new-grad feed (machine-readable JSON, updated through the day).

Each listing is tagged with its ATS so the apply stage knows whether it can fill it
(gh / ashby / lever) or whether the job needs an account the user creates (workday, icims, ...).

Output (workspace): feed_queue.json
"""
import json, os, re, sys, time, urllib.request

from engine.config import in_workspace
from engine.discovery.filters import load_domain, us_location

FEEDS = {
    "simplify-newgrad": "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
}
EXTRA_BAD = re.compile(r"technician|labeler|quality|test engineer|ts/sci|clearance", re.I)
NO_SPONSOR = ("U.S. Citizenship is Required", "Does Not Offer Sponsorship")


def ats_of(url):
    for key, name in (("greenhouse", "greenhouse"), ("ashbyhq", "ashby"), ("lever.co", "lever"),
                      ("myworkdayjobs", "workday"), ("icims", "icims")):
        if key in url:
            return name
    return "other"


def _needs_sponsorship():
    import json, os
    from engine.config import PROFILE
    p = os.path.join(PROFILE, "presets.json")
    return os.path.exists(p) and json.load(open(p, encoding="utf-8")).get("needs_sponsorship_now_or_future") == "Yes"


def pull(days=7, feed="simplify-newgrad", needs_sponsorship=None):
    needs_sponsorship = _needs_sponsorship() if needs_sponsorship is None else needs_sponsorship
    dom = load_domain()
    data = json.load(urllib.request.urlopen(FEEDS[feed], timeout=30))
    with in_workspace():
        applied = set(open("ids.txt").read().replace("\n", "").split(",")) if os.path.exists("ids.txt") else set()
        now, out = time.time(), []
        for x in data:
            if not x.get("active") or not x.get("is_visible", True) or now - x.get("date_posted", 0) > days * 86400:
                continue
            t, url, locs = x["title"], x.get("url", ""), ", ".join(x.get("locations", []))
            if not dom["include_titles"].search(t) and not re.search(r"developer|sde|swe", t, re.I):
                continue
            if dom["exclude_titles"].search(t) or EXTRA_BAD.search(t):
                continue
            if dom.get("exclude_companies") and dom["exclude_companies"].search(x["company_name"]):
                continue
            if not any(us_location(l) for l in x.get("locations") or [""]):
                continue
            if needs_sponsorship and x.get("sponsorship") in NO_SPONSOR:
                continue
            m = re.search(r"/jobs/(\d+)", url)
            if m and m.group(1) in applied:
                continue
            out.append(dict(source=feed, ats=ats_of(url), company=x["company_name"], title=t, url=url, location=locs,
                            posted=time.strftime("%m-%d", time.gmtime(x["date_posted"])), sponsorship=x.get("sponsorship")))
        out.sort(key=lambda r: r["posted"], reverse=True)
        json.dump(out, open("feed_queue.json", "w"), indent=1)
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out = pull(float(argv[0]) if argv else 7)
    for r in out:
        print(r["posted"], r["ats"], "|", r["company"], "|", r["title"][:60], "|", r["location"][:30], "|", r["url"][:80])
    print(len(out), "jobs -> workspace/feed_queue.json")


if __name__ == "__main__":
    main()
