"""The scout (11-11): keeps finding NEW places jobs are posted, so the applier never runs dry.

    python -m engine scout            one round now (prints what it found)
    python -m engine scout --loop 3   a round every 3 h (the `scout` container)
    python -m engine scout --report   yield per source so far

Each round has three drivers, all public, no accounts, a bounded number of small GETs:
  1. lists:  searches GitHub for job-list repos (new grad / entry level / internships). A README that links at least
             MIN_LINKS ATS boards becomes a harvest feed (sources.add_feed), so every later harvest reads it too.
  2. boards: public job APIs (Remotive, Arbeitnow, RemoteOK, The Muse, Himalayas, plus any in profile/scout.json
             "apis"). Their apply links that point at an ATS add that board directly.
  3. names:  employer names from those APIs and from local leads, not tried before, are probed on the guessable ATSs
             (Greenhouse, Ashby, Lever, Workable, SmartRecruiters), NAMES_PER_ROUND per round.
Everything lands in workspace/boards.json, which the pipeline's scan already reads: no new apply path. The fit gate,
trust gate and daily cap still decide what is applied to. Each source's yield (boards added, names, errors) is kept
in workspace/scout.json, so `--report` shows which drivers earn their calls and which to drop.
"""
import json, os, re, sys, time, urllib.parse, urllib.request

from engine.config import WORKSPACE
from engine.discovery import ats as A
from engine.feedback.events import record

STATE = os.path.join(WORKSPACE, "scout.json")
UA = {"User-Agent": "regen-engine scout (job discovery; public endpoints only)"}
MIN_LINKS = 15          # ATS boards a README must link to become a feed
REPOS_PER_ROUND = 20    # new repos looked at per round (one raw README GET each, two branch guesses)
NAMES_PER_ROUND = 100   # employer names probed per round (<= 2 slugs x 5 ATSs each)
QUERIES = ["new grad 2026 jobs", "new grad 2027", "entry level software engineer jobs", "university graduate jobs 2026",
           "summer 2027 internships", "ai engineer jobs list", "machine learning new grad", "embedded firmware jobs"]
APIS = {  # name -> (url, path to the job list, company field, url fields)
    "remotive": ("https://remotive.com/api/remote-jobs?category=software-dev", "jobs", "company_name", ("url",)),
    "arbeitnow": ("https://www.arbeitnow.com/api/job-board-api", "data", "company_name", ("url",)),
    "remoteok": ("https://remoteok.com/api", "", "company", ("apply_url", "url")),
    "themuse": ("https://www.themuse.com/api/public/jobs?category=Software%20Engineering&level=Entry%20Level&page=1",
                "results", "company.name", ("refs.landing_page",)),
    "himalayas": ("https://himalayas.app/jobs/api?limit=100", "jobs", "companyName", ("applicationLink",)),
}


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/json, text/plain, */*"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def _load():
    try:
        s = json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        s = {}
    for k, v in (("sources", {}), ("repos", {}), ("names", []), ("rounds", [])):
        s.setdefault(k, v)
    return s


def _save(s):
    s["names"] = s["names"][-20000:]
    s["rounds"] = s["rounds"][-200:]
    tmp = STATE + ".tmp"
    json.dump(s, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, STATE)


def _pick(obj, path):
    for k in path.split("."):
        obj = obj.get(k) if isinstance(obj, dict) else None
    return obj


def _tally(s, name, **kw):
    t = s["sources"].setdefault(name, {"runs": 0, "boards_added": 0, "names": 0, "errors": 0})
    t["runs"] += 1
    t["last"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    for k, v in kw.items():
        if k == "error":
            t["errors"] += 1
            t["last_error"] = str(v)[:160]
        else:
            t[k] = t.get(k, 0) + v


def add_board_urls(urls):
    """Every ATS board in these URLs that boards.json lacks -> added. Returns {ats: [tokens]} of the new ones."""
    found = A.harvest_urls(urls)
    b = A.load_boards()
    new = {}
    for a, toks in found.items():
        have = {x.lower() for x in b.get(a, [])}
        fresh = sorted(t for t in toks if t.lower() not in have)
        if fresh:
            b[a] = list(set(b.get(a, [])) | set(fresh))
            new[a] = fresh
    if new:
        A.save_boards(b)
    return new


def lists(s):
    """Driver 1: GitHub job-list repos -> feeds. One search per query (unauthenticated: 10/min), one README GET per
    new repo. Repos already looked at are never fetched again."""
    from engine.discovery.sources import add_feed, feeds
    known = set(feeds())
    seen, added = 0, 0
    for q in QUERIES:
        if seen >= REPOS_PER_ROUND:
            break
        try:
            data = json.loads(_get("https://api.github.com/search/repositories?" + urllib.parse.urlencode(
                {"q": f"{q} pushed:>{time.strftime('%Y-%m-%d', time.localtime(time.time() - 60 * 86400))}",
                 "sort": "updated", "per_page": 15})))
        except Exception as e:
            _tally(s, "github-search", error=e)
            break  # rate limited or offline: try again next round
        for r in data.get("items") or []:
            full = r.get("full_name")
            if not full or full in s["repos"] or seen >= REPOS_PER_ROUND:
                continue
            seen += 1
            url = f"https://raw.githubusercontent.com/{full}/{r.get('default_branch') or 'main'}/README.md"
            try:
                text = _get(url)
            except Exception as e:
                s["repos"][full] = {"ok": False, "why": type(e).__name__}
                continue
            boards = sum(len(t) for t in A.harvest_urls(re.findall(r"https?://[^\s)\]\"'<>]+", text)).values())
            s["repos"][full] = {"ok": boards >= MIN_LINKS, "boards": boards, "ts": time.strftime("%Y-%m-%d")}
            if boards >= MIN_LINKS and url not in known:
                res = add_feed(url, by="scout")
                added += res.get("boards_added", 0)
                known.add(url)
        time.sleep(7)  # stay under the unauthenticated search limit
    _tally(s, "github-lists", boards_added=added, repos=seen)
    return {"repos": seen, "boards_added": added}


def apis(s, extra=None):
    """Driver 2: public job APIs -> ATS boards in their apply links, and employer names for driver 3."""
    names, out = [], {}
    for name, (url, path, co, links) in {**APIS, **(extra or {})}.items():
        try:
            data = json.loads(_get(url))
            rows = _pick(data, path) if path else data
            rows = [r for r in rows or [] if isinstance(r, dict)]
        except Exception as e:
            _tally(s, name, error=e)
            out[name] = {"error": type(e).__name__}
            continue
        urls = [u for r in rows for f in links for u in [_pick(r, f)] if isinstance(u, str)]
        new = add_board_urls(urls)
        n = sum(len(t) for t in new.values())
        cos = [c.strip() for r in rows for c in [_pick(r, co)] if isinstance(c, str) and c.strip()]
        names += cos
        _tally(s, name, boards_added=n, names=len(set(cos)), jobs=len(rows))
        out[name] = {"jobs": len(rows), "boards_added": n}
    return out, names


def local_names():
    """Employer names the engine already met without a fillable board: leads (HN, alerts, VC portals)."""
    out = []
    for f in ("leads.json", "alert_leads.json"):
        try:
            data = json.load(open(os.path.join(WORKSPACE, f), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows = data if isinstance(data, list) else data.get("leads", []) if isinstance(data, dict) else []
        out += [str(r.get("company")) for r in rows if isinstance(r, dict) and r.get("company")]
    return out


def names(s, candidates):
    """Driver 3: untried employer names -> probe the guessable ATSs (sources.probe_companies, 50 per call)."""
    from engine.discovery.sources import probe_companies
    tried = {n.lower() for n in s["names"]}
    fresh = list({n.lower(): n for n in reversed(candidates)
                  if 2 <= len(n) <= 60 and n.lower() not in tried}.values())[::-1][:NAMES_PER_ROUND]  # first spelling wins
    found = 0
    for i in range(0, len(fresh), 50):
        try:
            found += len(probe_companies(fresh[i:i + 50], by="scout")["found"])
        except Exception as e:
            _tally(s, "probe", error=e)
    s["names"] += fresh
    _tally(s, "probe", boards_added=found, names=len(fresh))
    return {"probed": len(fresh), "boards_added": found}


def round_once():
    t0 = time.time()
    s = _load()
    extra = {}
    try:  # optional: more APIs the user (or an AI client) adds, same shape as APIS
        from engine.config import profile_file
        for k, v in (json.load(open(profile_file("scout.json"), encoding="utf-8")).get("apis") or {}).items():
            extra[k] = (v["url"], v.get("path", ""), v.get("company", "company"), tuple(v.get("links", ["url"])))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    before = sum(len(v) for k, v in A.load_boards().items() if k in A.ATS)
    r = {"lists": lists(s)}
    r["apis"], cos = apis(s, extra)
    r["names"] = names(s, cos + local_names())
    after = sum(len(v) for k, v in A.load_boards().items() if k in A.ATS)
    r.update(boards_before=before, boards_after=after, secs=round(time.time() - t0, 1))
    s["rounds"].append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "added": after - before, "secs": r["secs"]})
    _save(s)
    record("source", what="scout", added=after - before, by="scout")
    return r


def report():
    s = _load()
    rows = sorted(s["sources"].items(), key=lambda kv: -kv[1].get("boards_added", 0))
    print(f"{'source':<16}{'runs':>6}{'boards+':>9}{'names':>8}{'errors':>8}  last")
    for k, t in rows:
        print(f"{k:<16}{t['runs']:>6}{t.get('boards_added', 0):>9}{t.get('names', 0):>8}{t['errors']:>8}  {t.get('last', '')}"
              + (f"  ({t['last_error'][:50]})" if t.get("last_error") else ""))
    good = [k for k, v in s["repos"].items() if v.get("ok")]
    print(f"repos looked at: {len(s['repos'])}, became feeds: {len(good)}; names probed: {len(s['names'])}")
    for x in s["rounds"][-5:]:
        print(f"  round {x['ts']}: +{x['added']} boards in {x['secs']} s")


def main(argv=None):
    argv = sys.argv[2:] if argv is None else argv
    if "--report" in argv:
        return report()
    if "--loop" in argv:
        from engine.supervisor import beat
        i = argv.index("--loop")
        hours = float(argv[i + 1]) if len(argv) > i + 1 else 3.0
        while True:
            beat("scout", state="scouting")
            try:
                r = round_once()
                print(time.strftime("%H:%M"), "scout:", json.dumps(r), flush=True)
            except Exception as e:  # one bad round never stops the scout
                print("scout round failed:", type(e).__name__, e, flush=True)
            end = time.time() + hours * 3600
            while time.time() < end:
                beat("scout", state="sleeping until next round", next_s=round(end - time.time()))
                time.sleep(60)
    print(json.dumps(round_once(), indent=1))
