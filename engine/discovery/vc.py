"""`python -m engine vc [days] [--only next,yc,getro,consider] [--dry]`: venture-portfolio job portals as a source.

Startups backed by the big funds post on their fund's job portal long before they show up on the GitHub lists, so
each portal is read as *leads* (company + title + link) and resolved on the employer's own ATS, like newgrad:
  next      fund portals built on Next.js server actions (hosts in profile/vc_portals.json "next_action", kept out of
            the repo): the page's own "loadMorePublicJobs" action (id read from its JS bundle each run, it changes
            with each deploy), engineering roles posted in the last `days`, 100 a page.
  yc        ycombinator.com/jobs role pages (software engineer, all + per city; 40 postings each, visa field kept),
            plus YC companies marked hiring (yc-oss.github.io API) probed for a Greenhouse / Ashby / Lever board,
            120 not-yet-probed companies a run (workspace/vc_state.json), so boards grow without a burst of calls.
  getro     Getro-hosted fund portals (General Catalyst, Accel, Khosla, ...): public search API, keyword queries.
  consider  Consider-hosted fund portals (Sequoia, GV, Kleiner, Bessemer, First Round, ...): search API behind the
            page's CSRF token + session cookie.
A lead whose link is already an ATS posting seeds the resolve cache with that board, so it is matched exactly; other
links (company career pages, Comeet, Workday) go through the usual slug guesses, else to workspace/leads.json.
Only public job pages are read; nothing is submitted here: the fit gate, trust gate and caps still decide.
"""
import http.cookiejar, json, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone

from engine.config import WORKSPACE
from engine.discovery import ats as A
from engine.discovery.filters import keep, load_domain

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
QUERIES = ("software engineer", "machine learning engineer", "data engineer", "backend engineer", "full stack engineer")
GETRO = ("jobs.generalcatalyst.com", "jobs.accel.com", "jobs.khoslaventures.com")
CONSIDER = ("jobs.sequoiacap.com", "jobs.lsvp.com", "jobs.kleinerperkins.com", "jobs.gv.com", "jobs.bvp.com",
            "jobs.firstround.com")
YC_ROLES = ("software-engineer",)
YC_CITIES = ("", "san-francisco", "new-york", "los-angeles", "seattle", "austin", "chicago")
STATE = os.path.join(WORKSPACE, "vc_state.json")
YC_PROBE_PER_RUN = 120


def _open(url, data=None, headers=None, opener=None, timeout=40):
    h = {"User-Agent": UA, **(headers or {})}
    req = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data, headers=h)
    return (opener.open if opener else urllib.request.urlopen)(req, timeout=timeout).read().decode("utf-8", "replace")


def _lead(company, title, location, url, posted=None, h1b=None, portal="", domain=None):
    return dict(company=(company or "").strip(), title=(title or "").strip(), location=(location or "").strip(),
                lead_url=url or "", posted=posted, h1b=h1b, portal=portal, domain=domain)


def portals():
    """profile/vc_portals.json: {"next_action": [host], "getro": [host], "consider": [host]} (optional)."""
    from engine.config import PROFILE
    try:
        return json.load(open(os.path.join(PROFILE, "vc_portals.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ---- Next.js server-action portals ------------------------------------------------------------------------------
def next_action_id(host):
    """Server-action id of loadMorePublicJobs; it changes with each deploy of the portal, so it is read every run."""
    page = _open(f"https://{host}/jobs")
    for src in dict.fromkeys(re.findall(r'/_next/static/chunks/[^"]+\.js', page)):
        js = _open(f"https://{host}" + src)
        m = re.search(r'createServerReference\)\("([0-9a-f]{40,})",[^)]*"loadMorePublicJobs"\)', js)
        if m:
            return m.group(1)
    raise RuntimeError(f"{host}: loadMorePublicJobs action not found in the page bundle")


def next_portals(days=2, pages=6):
    out = []
    for host in portals().get("next_action", []):
        try:
            out += _next_portal(host, days, pages)
        except Exception as e:
            print("  ! next", host, e)
    return out


def _next_portal(host, days, pages):
    aid, out = next_action_id(host), []
    for p in range(1, pages + 1):
        body = json.dumps([{"roles": ["engineering"], "postedWithinDays": max(1, int(days)), "sort": "recent"},
                           {"page": p, "limit": 100}])
        raw = _open(f"https://{host}/jobs", body, {"Next-Action": aid, "Accept": "text/x-component",
                                                         "Content-Type": "text/plain;charset=UTF-8"})
        line = next((l for l in raw.splitlines() if l.startswith("1:")), None)
        if not line:
            break
        d = json.loads(line[2:])
        for j in d.get("jobs", []):
            out.append(_lead(j.get("company_name"), j.get("title"), j.get("location") or "; ".join(j.get("locations") or []),
                             j.get("apply_url"), j.get("posted_at"), portal=host))
        if d.get("isDone") or not d.get("jobs"):
            break
    return out


# ---- Y Combinator -----------------------------------------------------------------------------------------------
_YC_COS = {}


def yc_companies():
    """yc-oss list of YC companies marked hiring (name, website, regions), fetched once a run."""
    if not _YC_COS:
        try:
            _YC_COS.update({c["name"]: c for c in json.loads(_open("https://yc-oss.github.io/api/companies/hiring.json", timeout=90))})
        except Exception as e:
            print("  ! yc-oss", e)
    return _YC_COS


def yc_jobs():
    import html
    out, sites = [], {n: c.get("website") for n, c in yc_companies().items()}
    for role in YC_ROLES:
        for city in YC_CITIES:
            url = f"https://www.ycombinator.com/jobs/role/{role}" + (f"/{city}" if city else "")
            try:
                m = re.search(r'data-page="([^"]*)"', _open(url))
                posts = json.loads(html.unescape(m.group(1)))["props"].get("jobPostings", []) if m else []
            except Exception as e:
                print("  ! yc", url, e)
                continue
            for j in posts:
                visa = j.get("visa") or ""
                out.append(_lead(j.get("companyName"), j.get("title"), j.get("location"),
                                 "https://www.ycombinator.com" + (j.get("url") or ""),
                                 h1b=True if visa == "Will sponsor" else None, portal="yc",
                                 domain=sites.get(j.get("companyName"))))
    return out


def yc_probe(limit=YC_PROBE_PER_RUN):
    """YC companies marked hiring -> boards on the guessable ATSs. Each company is probed once (state file)."""
    from engine.discovery.sources import probe_companies
    cos = list(yc_companies().values())
    if not cos:
        return {"error": "yc-oss list unavailable"}
    st = _state()
    done = set(st.get("yc_probed", []))
    todo = [c for c in cos if c.get("status") == "Active" and c.get("name") not in done
            and any(r in (c.get("regions") or []) for r in ("United States of America", "America / Canada", "Remote"))]
    todo.sort(key=lambda c: c.get("launched_at") or 0, reverse=True)  # newest batches first: smallest, least-known
    found, tried = [], 0
    for i in range(0, min(limit, len(todo)), 50):  # probe_companies takes 50 names a call
        names = [c["name"] for c in todo[i:i + 50]][: limit - i]
        r = probe_companies(names, by="vc:yc")
        found += r.get("found", [])
        tried += r.get("tried", 0)
        done.update(names)
    st["yc_probed"] = sorted(done)
    _save_state(st)
    return {"companies": len(cos), "probed_now": min(limit, len(todo)), "left": max(0, len(todo) - limit),
            "gets": tried, "boards_found": found}


# ---- Getro fund portals -----------------------------------------------------------------------------------------
def getro(days=2, hosts=GETRO, queries=QUERIES, per=100):
    out, cut = [], (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    for host in hosts:
        try:
            nid = re.search(r'"network":\{"id":"?(\d+)', _open(f"https://{host}/jobs")).group(1)
        except Exception as e:
            print("  ! getro", host, e)
            continue
        for q in queries:
            for page in range(3):
                try:
                    d = json.loads(_open(f"https://api.getro.com/api/v2/collections/{nid}/search/jobs",
                                         json.dumps({"hitsPerPage": per, "page": page, "filters": "", "query": q}),
                                         {"Content-Type": "application/json", "Accept": "application/json",
                                          "Origin": f"https://{host}", "Referer": f"https://{host}/"}))
                except Exception as e:
                    print("  ! getro", host, q, e)
                    break
                jobs = (d.get("results") or {}).get("jobs") or []
                fresh = [j for j in jobs if (j.get("created_at") or 0) >= cut]
                for j in fresh:
                    out.append(_lead((j.get("organization") or {}).get("name"), j.get("title"),
                                     "; ".join(j.get("locations") or []), j.get("url"),
                                     datetime.fromtimestamp(j["created_at"], timezone.utc).isoformat(), portal=host))
                if len(jobs) < per or len(fresh) < len(jobs) // 2:  # results are newest-first enough: stop paging
                    break
    return out


# ---- Consider fund portals --------------------------------------------------------------------------------------
def consider(days=2, hosts=CONSIDER, queries=QUERIES, per=100):
    out, cut = [], datetime.now(timezone.utc) - timedelta(days=days)
    for host in hosts:
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        try:
            page = _open(f"https://{host}/jobs", opener=op)
            board = re.search(r'"fixedBoard":"([^"]+)"', page).group(1)
            token = re.search(r'"csrfToken":"([^"]+)"', page).group(1)
        except Exception as e:
            print("  ! consider", host, e)
            continue
        for q in queries:
            seq = None
            for _ in range(3):
                body = {"meta": {"size": per, **({"sequence": seq} if seq else {})},
                        "board": {"id": board, "isParent": True},
                        "query": {"promoteFeatured": False, "keywords": q}, "grouped": False}
                try:
                    d = json.loads(_open(f"https://{host}/api-boards/search-jobs", json.dumps(body),
                                         {"Content-Type": "application/json", "Accept": "application/json",
                                          "x-csrf-token": token, "Origin": f"https://{host}",
                                          "Referer": f"https://{host}/jobs"}, opener=op))
                except Exception as e:
                    print("  ! consider", host, q, e)
                    break
                jobs = d.get("jobs") or []
                fresh = [j for j in jobs if j.get("timeStamp") and datetime.fromisoformat(j["timeStamp"].replace("Z", "+00:00")) >= cut]
                for j in fresh:
                    out.append(_lead(j.get("companyName"), j.get("title"), "; ".join(j.get("locations") or []),
                                     j.get("applyUrl") or j.get("url"), j.get("timeStamp"), portal=host,
                                     domain=j.get("companyDomain")))
                seq = (d.get("meta") or {}).get("sequence")
                if not seq or len(jobs) < per or len(fresh) < len(jobs) // 2:
                    break
    return out


# ---- common -----------------------------------------------------------------------------------------------------
def _state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(st):
    tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, STATE)


def ats_of(url):
    """(ats, token) when a lead link is itself a posting on a board the engine reads, else None."""
    for a, toks in A.harvest_urls([url]).items():
        if toks and a in A.OPEN_ATS + A.FILLED:
            return a, next(iter(toks))
    return None


CAREER_PATHS = ("/careers", "/jobs", "/company/careers", "")


def crawl_careers(lead):
    """(ats, token) found on the startup's own pages: the lead link itself when it is the company's site (a career
    page that embeds Greenhouse with gh_jid, say), then <domain>/careers, /jobs, /company/careers and the home page.
    At most 5 GETs a company, cached for a week either way (vc_state.json "careers")."""
    pages = []
    host = re.sub(r"^https?://", "", lead.get("lead_url") or "").split("/")[0]
    if host and not re.search(r"ycombinator\.com|getro\.com|consider\.com|linkedin\.com", host) \
            and host not in portals().get("next_action", []):
        pages.append(lead["lead_url"])
    dom = re.sub(r"^https?://|/.*$", "", lead.get("domain") or "") or (host if pages else "")
    pages += [f"https://{dom}{p}" for p in CAREER_PATHS] if dom else []
    for u in dict.fromkeys(pages):
        try:
            text = _open(u, timeout=20)
        except Exception:
            continue
        found = A.harvest_urls(re.findall(r"https?://[^\s\"'<>)]+", text) + re.findall(r"//[a-z0-9.-]+\.(?:greenhouse\.io|ashbyhq\.com|lever\.co)[^\s\"'<>)]*", text))
        for a in A.OPEN_ATS + A.FILLED + ("workday", "smartrecruiters"):
            if found.get(a):
                return a, sorted(found[a])[0]
        m = re.search(r"greenhouse\.io/embed/job_board(?:/js)?\?for=([A-Za-z0-9_-]+)", text)
        if m:
            return "greenhouse", m.group(1).lower()
    return None


def careers(leads, ttl_days=7):
    """Unresolved leads -> boards from each company's own site; returns the leads whose board was found."""
    import concurrent.futures as cf
    st = _state()
    seen = st.setdefault("careers", {})
    today = datetime.now(timezone.utc).date()
    todo = {}
    for l in leads:
        c = seen.get(l["company"])
        if isinstance(c, list):
            continue  # board known already; resolve did not match the title there
        if isinstance(c, str) and (today - datetime.fromisoformat(c).date()).days < ttl_days:
            continue
        todo.setdefault(l["company"], l)
    with cf.ThreadPoolExecutor(12) as ex:
        hits = dict(zip(todo, ex.map(crawl_careers, todo.values())))
    for co, at in hits.items():
        seen[co] = list(at) if at else today.isoformat()
    _save_state(st)
    return {co: at for co, at in hits.items() if at}


def gate(leads):
    """Fit gate on title/location/company before any board fetch, then one lead per (company, title)."""
    dom, seen, out, dropped = load_domain(), set(), [], {}
    for l in leads:
        if not l["company"] or not l["title"]:
            continue
        why = keep(dom, l["title"], l["location"], l["company"])
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        k = (l["company"].lower(), l["title"].lower())
        if k not in seen:
            seen.add(k)
            out.append(l)
    return out, dropped


def ingest(leads, source):
    """Leads -> employer ATS (queue.json) or leads.json. Direct ATS links pin the company's board in the cache."""
    from engine.discovery.newgrad import resolve
    from engine.discovery.scan import filter_jobs, merge_queue
    from engine.discovery.sources import add_boards
    cache_p = os.path.join(WORKSPACE, "resolve_cache.json")
    try:
        cache = json.load(open(cache_p, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    direct = [l["lead_url"] for l in leads if ats_of(l["lead_url"])]
    for l in leads:
        at = ats_of(l["lead_url"])
        if at and not (cache.get(l["company"]) or {}).get("board"):
            cache[l["company"]] = {"board": list(at)}
    json.dump(cache, open(cache_p, "w", encoding="utf-8"), indent=1)
    for i in range(0, len(direct), 50):  # add_boards takes 50 a call
        add_boards(direct[i:i + 50], by=source)
    resolved, unresolved = resolve(leads, source=source)
    found = careers(unresolved)  # startups that only post on their own site: look for the ATS behind it
    if found:
        cache = json.load(open(cache_p, encoding="utf-8"))
        b = A.load_boards()
        for co, (a, tok) in found.items():
            cache[co] = {"board": [a, tok]}
            if tok not in b.setdefault(a, []):
                b[a].append(tok)
        json.dump(cache, open(cache_p, "w", encoding="utf-8"), indent=1)
        A.save_boards(b)
        again = [l for l in unresolved if l["company"] in found]
        more, unresolved2 = resolve(again, source=source + "+careers")
        resolved += more
        unresolved = [l for l in unresolved if l["company"] not in found] + unresolved2
        print(f"   careers pages: {len(found)} boards found, {len(more)} more leads resolved")
    now = datetime.now(timezone.utc).isoformat()
    fresh, dropped = filter_jobs([{**j, "posted": j.get("posted") or now} for j in resolved], 3650)
    q = merge_queue(fresh)
    p = os.path.join(WORKSPACE, "leads.json")
    try:
        old = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        old = []
    have = {(x.get("company"), x.get("title")) for x in old}
    json.dump(old + [u for u in unresolved if (u["company"], u["title"]) not in have], open(p, "w", encoding="utf-8"), indent=1)
    return fresh, unresolved, dropped, len(q)


def yc_direct(unresolved):
    """YC leads with no employer ATS -> queue jobs (ats "yc") when the posting page has its own no-account apply form
    (showDirectApply: name, email, LinkedIn, phone, city, work authorization, sponsorship, resume, a note). The runner
    fills that form (fill_yc). One page GET per lead; the rest stay Work-at-a-Startup only (yc_waas.md)."""
    import concurrent.futures as cf
    leads = [l for l in unresolved if "ycombinator.com/companies/" in (l.get("lead_url") or "")]
    with cf.ThreadPoolExecutor(8) as ex:
        props = list(ex.map(lambda l: A.yc_job(l["lead_url"]), leads))
    now, jobs, rest = datetime.now(timezone.utc).isoformat(), [], [l for l in unresolved if l not in leads]
    for l, p in zip(leads, props):
        if not p or not p.get("showDirectApply"):
            rest.append(l)
            continue
        j = p.get("job") or {}
        jobs.append({"id": f"yc-{j.get('id') or l['lead_url'].rsplit('/', 1)[-1]}", "ats": "yc",
                     "token": (j.get("companyUrl") or "").rsplit("/", 1)[-1], "company": l["company"],
                     "title": l["title"], "location": l["location"], "url": l["lead_url"].split("?")[0],
                     "posted": now, "source": "vc:yc", "h1b": l.get("h1b"), "visa": j.get("visa")})
    return jobs, rest


def waas(unresolved):
    """YC postings with no public ATS: they take applications only through Work at a Startup (one YC profile, the
    user's account), so they are listed for the user in workspace/yc_waas.md instead of being dropped."""
    rows = [l for l in unresolved if "ycombinator.com" in (l.get("lead_url") or "")]
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# YC roles that apply only through Work at a Startup ({stamp})", "",
             "Sign in once at workatastartup.com; each link opens the posting. Fit-gated (title, US, level).", ""]
    lines += [f"- [{l['company']} - {l['title']}]({l['lead_url']}) | {l['location'][:40]}"
              + (" | sponsors visas" if l.get("h1b") else "") for l in rows]
    with open(os.path.join(WORKSPACE, "yc_waas.md"), "w", encoding="utf-8") as fh:
        fh.write(chr(10).join(lines) + chr(10))
    return len(rows)


DRIVERS = {"next": next_portals, "yc": lambda days: yc_jobs(),
           "getro": lambda days: getro(days, tuple(portals().get("getro", GETRO))),
           "consider": lambda days: consider(days, tuple(portals().get("consider", CONSIDER)))}


def main(argv=None):
    from engine.feedback.events import record
    argv = sys.argv[1:] if argv is None else argv
    days = float(next((a for a in argv if re.fullmatch(r"[\d.]+", a)), 2))
    only = next((a.split("=", 1)[1] for a in argv if a.startswith("--only=")), None)
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    names = only.split(",") if only else list(DRIVERS) + ["ycprobe"]
    dry = "--dry" in argv
    st = _state()
    last = st.get("last_run")
    if not dry and not only and "--force" not in argv and last and (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() < 3600:
        print(f"vc: ran at {last[:16]} (< 60 min ago), skipped; --force to run anyway")
        return {}
    if not dry and not only:
        st["last_run"] = datetime.now(timezone.utc).isoformat()
        _save_state(st)
    total = {}
    for name in names:
        if name == "ycprobe":
            r = {"skipped": "dry run"} if dry else yc_probe()
            print(f"ycprobe: {r}")
            total[name] = r
            continue
        try:
            raw = DRIVERS[name](days)
        except Exception as e:
            print(f"  ! {name}: {e}")
            total[name] = {"error": str(e)[:200]}
            continue
        leads, gated = gate(raw)
        print(f"{name}: {len(raw)} postings, {len(leads)} past the fit gate; gated {dict(sorted(gated.items(), key=lambda x: -x[1])[:6])}")
        if dry:
            for l in leads[:15]:
                print(f"   {l['company'][:24]:24} | {l['title'][:58]:58} | {(ats_of(l['lead_url']) or ('?',))[0]}")
            total[name] = {"postings": len(raw), "leads": len(leads)}
            continue
        fresh, unresolved, dropped, qn = ingest(leads, f"vc:{name}")
        for j in fresh[:40]:
            print(f"   + {j['id']} | {j['ats'][:2]} | {j['company'][:22]} | {j['title'][:60]} | {j['location'][:28]}")
        print(f"{name}: {len(fresh)} queued (queue {qn}), {len(unresolved)} unresolved -> leads.json, dropped {dropped}")
        total[name] = {"postings": len(raw), "leads": len(leads), "queued": len(fresh), "unresolved": len(unresolved)}
        if name == "yc":
            direct, rest = yc_direct(unresolved)
            from engine.discovery.scan import filter_jobs, merge_queue
            ok, why = filter_jobs(direct, 3650)
            qn = len(merge_queue(ok))
            print(f"yc: {len(ok)} roles with the page's own apply form queued as ats=yc (queue {qn}), dropped {why}")
            total[name]["direct"] = len(ok)
            waas(rest)
        record("source", what="vc", portal=name, postings=len(raw), leads=len(leads), queued=len(fresh),
               unresolved=len(unresolved))
    return total


if __name__ == "__main__":
    main()
