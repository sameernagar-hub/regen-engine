"""Source-first discovery: poll company Greenhouse boards directly.

A posting appears on boards-api.greenhouse.io as soon as the recruiter publishes it,
hours or days before it is syndicated to LinkedIn/Indeed.

Inputs (workspace):  boards.txt  comma-separated board tokens (falls back to engine/discovery/boards.example.txt)
                     ids.txt     job ids already applied to (dedupe)
Profile:             domains.json  title include/exclude regexes + location rules for your domain
Output (workspace):  queue.json
"""
import json, os, re, sys, urllib.request, concurrent.futures as cf
from datetime import datetime, timezone, timedelta

from engine.config import PACKAGE, PROFILE, in_workspace

DEFAULT_DOMAIN = {
    "include_titles": r"software|full.?stack|backend|back-end|ai engineer|machine learning engineer|ml engineer|forward.?deployed|platform engineer|product engineer|applied ai|founding engineer|member of technical staff",
    "exclude_titles": r"senior|sr\.|staff|principal|\blead\b|manager|director|head of|intern\b|internship|apprentice|firmware|embedded|hardware|silicon|asic|verification|security clearance|\biii\b|\biv\b|\b[345]\b",
    "include_locations": r"remote|united states|\bUS\b|USA|, [A-Z]{2}\b|San Francisco|New York|Seattle|Austin|Boston|Los Angeles|Palo Alto|Mountain View|San Jose|Sunnyvale|Bay Area|Chicago|Denver",
    "exclude_locations": r"\bUK\b|London|Canada|Toronto|India|Bangalore|Bengaluru|Dublin|Germany|Berlin|Paris|Singapore|Tokyo|Sydney|Amsterdam|Poland|Mexico|Brazil|Israel|Tel Aviv",
}


def load_domain():
    path = os.path.join(PROFILE, "domains.json")
    d = dict(DEFAULT_DOMAIN)
    if os.path.exists(path):
        d.update(json.load(open(path)))
    return {k: re.compile(v, re.I) for k, v in d.items()}


def load_boards():
    path = "boards.txt" if os.path.exists("boards.txt") else os.path.join(PACKAGE, "discovery", "boards.example.txt")
    return [t.strip() for t in open(path).read().replace("\n", ",").split(",") if t.strip()]


def load_applied():
    return set(open("ids.txt").read().replace("\n", "").split(",")) if os.path.exists("ids.txt") else set()


def scan_board(token, dom, applied, cut):
    try:
        d = json.load(urllib.request.urlopen(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", timeout=20))
    except Exception:
        return []
    out = []
    for j in d.get("jobs", []):
        ts = j.get("first_published") or j.get("updated_at")
        if not ts:
            continue
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if when < cut or str(j["id"]) in applied:
            continue
        title, loc = j["title"], (j.get("location") or {}).get("name", "")
        if not dom["include_titles"].search(title) or dom["exclude_titles"].search(title):
            continue
        if dom["exclude_locations"].search(loc) and not re.search(r"United States|, [A-Z]{2}\b(?<!UK)", loc):
            continue
        if loc and not dom["include_locations"].search(loc):
            continue
        out.append(dict(source="greenhouse", token=token, id=j["id"], company=j.get("company_name") or token, title=title,
                        location=loc, posted=when.strftime("%m-%d %H:%M"), url=j["absolute_url"]))
    return out


def scan(days=3):
    with in_workspace():
        dom, applied, boards = load_domain(), load_applied(), load_boards()
        cut = datetime.now(timezone.utc) - timedelta(days=days)
        out = []
        with cf.ThreadPoolExecutor(24) as ex:
            for r in ex.map(lambda t: scan_board(t, dom, applied, cut), boards):
                out += r
        out.sort(key=lambda r: r["posted"], reverse=True)
        json.dump(out, open("queue.json", "w"), indent=1)
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out = scan(float(argv[0]) if argv else 3)
    for r in out:
        print(r["id"], "|", r["posted"], "|", r["company"], "|", r["title"], "|", r["location"][:35])
    print(len(out), "jobs -> workspace/queue.json")


if __name__ == "__main__":
    main()
