"""Discovery sources an AI client can grow over MCP (engine/connectors/mcp_server.py, discovery level).

Everything lands where the discover stage already reads, so the next pipeline pass scans it with no new code path:
  boards  -> workspace/boards.json      (any ATS board / job URL, or company names probed on the sluggable ATSs)
  feeds   -> workspace/sources.json     (job-list READMEs / JSON with ATS links; harvested now and by `engine harvest`)
  leads   -> resolved on the employer's own ATS -> workspace/queue.json; unresolved ones -> workspace/leads.json
Each add is an audited `source` event (what, how many, by whom). Only public job pages are fetched; nothing is
submitted from here: the fit gate, trust gate and caps still decide what gets applied to.
"""
import json, os, re, urllib.request

from engine.config import WORKSPACE
from engine.discovery import ats as A
from engine.feedback.events import read, record

SOURCES = os.path.join(WORKSPACE, "sources.json")
MAX_ADD = 50  # per call: keeps one request from fanning out into hundreds of board fetches


def _load():
    try:
        return json.load(open(SOURCES, encoding="utf-8"))
    except (OSError, ValueError):
        return {"feeds": []}


def feeds():
    """Built-in harvest feeds plus the ones added over MCP."""
    return list(dict.fromkeys(A.HARVEST_FEEDS + [f["url"] for f in _load().get("feeds", [])]))


def stats():
    b = A.load_boards()
    try:
        queue = len(json.load(open(os.path.join(WORKSPACE, "queue.json"), encoding="utf-8")))
    except (OSError, ValueError):
        queue = None
    added = read("source")
    return {"boards": {a: len(set(v)) for a, v in b.items()}, "boards_total": sum(len(set(v)) for v in b.values()),
            "queue": queue, "feeds_builtin": len(A.HARVEST_FEEDS), "feeds_added": _load().get("feeds", []),
            "recent_adds": added[-10:]}


def add_boards(items, by="mcp"):
    """Board tokens from job / board URLs (any ATS the engine knows). Tokens already watched are skipped."""
    urls = [str(u) for u in items][:MAX_ADD]
    found = A.harvest_urls(urls)
    b = A.load_boards()
    new = {a: sorted(t - {x.lower() for x in b.get(a, [])} - set(b.get(a, []))) for a, t in found.items()}
    for a, toks in new.items():
        b[a] = list(set(b.get(a, [])) | set(toks))
    A.save_boards(b)
    added = {a: t for a, t in new.items() if t}
    record("source", what="boards", added=sum(len(t) for t in added.values()), by=by)
    unknown = [u for u in urls if not any(re.search(p, u) for p in A.HARVEST.values())]
    return {"added": added, "not_an_ats_url": unknown[:20]}


def add_feed(url, by="mcp"):
    """A job list (README or JSON) with ATS links: fetched once now, its boards added, and kept for later harvests."""
    if not re.match(r"https://", url or ""):
        return {"error": "feeds must be https URLs"}
    try:
        text = urllib.request.urlopen(urllib.request.Request(url, headers=A.UA), timeout=60).read().decode("utf-8", "replace")
    except Exception as e:
        return {"error": f"fetch failed: {type(e).__name__}"}
    links = re.findall(r"https?://[^\s)\]\"'<>]+", text)
    found, b = A.harvest_urls(links), A.load_boards()  # a whole list in one pass, same as `engine harvest`
    new = {a: sorted(t - set(b.get(a, []))) for a, t in found.items()}
    for a, toks in new.items():
        b[a] = list(set(b.get(a, [])) | set(toks))
    A.save_boards(b)
    r = {"added": {a: t for a, t in new.items() if t}}
    n = sum(len(t) for t in r["added"].values())
    s = _load()
    if url not in {f["url"] for f in s["feeds"]} and url not in A.HARVEST_FEEDS:
        s["feeds"].append({"url": url, "links": len(links), "boards_added": n, "by": by})
        tmp = SOURCES + ".tmp"
        json.dump(s, open(tmp, "w", encoding="utf-8"), indent=1)
        os.replace(tmp, SOURCES)
    record("source", what="feed", url=url, links=len(links), added=n, by=by)
    return {"links": len(links), "boards_added": n, "added": {a: t[:20] for a, t in r["added"].items()}}


def probe_companies(names, by="mcp"):
    """Company names -> boards on the ATSs whose tokens can be guessed (one GET per guess, 16 at a time)."""
    import concurrent.futures as cf
    from engine.discovery.probe import URLS, _has_jobs, slugs
    b = A.load_boards()
    known = {a: {s.lower() for s in b.get(a, [])} for a in URLS}
    tasks = [(a, s) for n in [str(x) for x in names][:MAX_ADD] for s in slugs(n) for a in URLS if s not in known[a]]
    found = []
    with cf.ThreadPoolExecutor(16) as ex:
        for (a, s), ok in zip(tasks, ex.map(lambda t: _has_jobs(*t), tasks)):
            if ok:
                found.append([a, s])
                b.setdefault(a, []).append(s)
    A.save_boards(b)
    record("source", what="probe", tried=len(tasks), added=len(found), by=by)
    return {"tried": len(tasks), "found": found}


def add_leads(leads, by="mcp"):
    """Job leads [{company, title, url?}] seen anywhere: matched on the employer's own ATS -> queue; else leads.json."""
    from datetime import datetime, timezone
    from engine.discovery.newgrad import resolve
    from engine.discovery.scan import filter_jobs, merge_queue
    clean = [{"company": str(l.get("company", "")).strip(), "title": str(l.get("title", "")).strip(),
              "lead_url": str(l.get("url", "")), "h1b": l.get("h1b")} for l in leads[:MAX_ADD]
             if l.get("company") and l.get("title")]
    if not clean:
        return {"error": "each lead needs company and title"}
    add_boards([l["lead_url"] for l in clean if l["lead_url"]], by=by)  # a lead URL on an ATS is itself a board
    resolved, unresolved = resolve(clean, source=f"lead:{by}")
    fresh, dropped = filter_jobs([{**j, "posted": j.get("posted") or datetime.now(timezone.utc).isoformat()} for j in resolved], 3650)
    q = merge_queue(fresh)
    p = os.path.join(WORKSPACE, "leads.json")
    try:
        old = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        old = []
    json.dump(old + unresolved, open(p, "w", encoding="utf-8"), indent=1)
    record("source", what="leads", given=len(clean), queued=len(fresh), unresolved=len(unresolved), by=by)
    return {"queued": [f"{j['company']} - {j['title']}" for j in fresh], "unresolved": len(unresolved),
            "dropped": dropped, "queue": len(q)}
