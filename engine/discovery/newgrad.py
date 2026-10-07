"""`python -m engine newgrad [days]`: newgrad-jobs.com (Airtable-backed, ~150 new SWE rows a day).

Its apply links go through jobright.ai and hide the employer's real posting, so each row is a *lead*:
we resolve the company to its own Greenhouse / Ashby / Lever board and find the same title there.
  resolved   -> merged into workspace/queue.json (apply at the source, like every other job)
               and the board is added to boards.json, so future scans watch it directly
  unresolved -> workspace/leads.json (Workday / iCIMS / custom portals: a human applies)

Resolution results are cached in workspace/resolve_cache.json (company -> board or null).
"""
import difflib, json, os, re, sys, concurrent.futures as cf
from datetime import datetime, timezone

from engine.config import WORKSPACE
from engine.discovery import ats as A
from engine.discovery.airtable import read_view
from engine.discovery.filters import load_domain, keep, norm
from engine.discovery.scan import filter_jobs, merge_queue

VIEWS = {  # newgrad-jobs.com tabs relevant to a software profile
    "swe": "https://airtable.com/embed/appjDG7vmPOm1pO7S/shr763VHjlzPBDCgN",
    "aiml": "https://airtable.com/embed/appoxNzAIRReFCzZV/shrmDBF1vNPtzNjzl",
    "de": "https://airtable.com/embed/appqYfRGKpLQ8UsdH/shrFnvW20reJCEkYZ",
}
SUFFIX = re.compile(r"\b(inc|llc|ltd|corp|corporation|co|company|group|holdings|technologies|technology|labs?|the|ai|hq|usa|us|global|software|systems)\b", re.I)


def slugs(company):
    base = re.sub(r"[^a-z0-9 ]", "", company.lower().replace("&", "and"))
    words = base.split()
    core = [w for w in words if not SUFFIX.fullmatch(w)] or words
    c = {"".join(words), "".join(core), "-".join(core), "".join(core[:1]), "".join(core[:2]), core[-1]}
    return [s for s in c if len(s) >= 3]


def pull(days=1, views=("swe", "aiml", "de")):
    dom = load_domain()
    today = datetime.now(timezone.utc).date()
    rows = []
    for v in views:
        try:
            for r in read_view(VIEWS[v]):
                r["_view"] = v
                rows.append(r)
        except Exception as e:
            print("  ! newgrad view", v, e)
    leads, seen = [], set()
    for r in rows:
        title, co, loc = r.get("Position Title") or "", r.get("Company") or "", r.get("Location") or ""
        try:
            age = (today - datetime.strptime(str(r.get("Date"))[:10], "%Y-%m-%d").date()).days
        except ValueError:
            continue
        if age > days or keep(dom, title, loc, co) or (co, title) in seen:
            continue
        seen.add((co, title))
        leads.append(dict(company=co, title=title, location=loc, date=str(r.get("Date"))[:10], view=r["_view"],
                          h1b=r.get("H1b Sponsored"), new_grad=r.get("Is New Grad"), salary=r.get("Salary"),
                          quals=(r.get("Qualifications") or "")[:600], lead_url=(r.get("Apply") or {}).get("url")))
    return leads


def _match(jobs, title):
    """Best posting on a board for a lead title: exact normalized title, else a close fuzzy match."""
    want = norm(title)
    exact = [j for j in jobs if norm(j["title"]) == want]
    pool = exact or [j for j in jobs if difflib.SequenceMatcher(None, norm(j["title"]), want).ratio() >= 0.88]
    return max(pool, key=lambda j: j.get("posted") or "") if pool else None


def resolve(leads, miss_ttl_days=7, source="newgrad-jobs"):
    """Find each lead on its employer's own ATS board.

    Cache (workspace/resolve_cache.json):  company -> {"board": [ats, token]}  only after a lead title matched there
                                                     {"miss": "YYYY-MM-DD"}     nothing matched; retried after a week
    A slug can belong to a different company (e.g. ashby:pylon), so a board is never trusted on its name alone."""
    cache_p = os.path.join(WORKSPACE, "resolve_cache.json")
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
    cache = {k: v for k, v in cache.items() if isinstance(v, dict)}  # drop the unverified v0.4.0 format
    boards = A.load_boards()
    today = datetime.now(timezone.utc).date()
    companies = sorted({l["company"] for l in leads})

    def candidates(co):
        c = cache.get(co, {})
        if c.get("board"):
            return [tuple(c["board"])]
        if c.get("miss") and (today - datetime.fromisoformat(c["miss"]).date()).days < miss_ttl_days:
            return []                                   # saves ~15 calls per company per run
        return [(a, s) for s in slugs(co) for a in A.ATS]

    def board_jobs(at):
        try:
            return at, A.FETCH[at[0]](at[1])
        except Exception:
            return at, None

    todo = {at for co in companies for at in candidates(co)}
    with cf.ThreadPoolExecutor(32) as ex:
        fetched = dict(ex.map(board_jobs, todo))
    resolved, unresolved = [], []
    for co in companies:
        cands = [at for at in candidates(co) if fetched.get(at)]
        for l in (x for x in leads if x["company"] == co):
            hit, board = None, None
            for at in cands:
                hit = _match(fetched[at], l["title"])
                if hit:
                    board = at; break
            if hit:
                cache[co] = {"board": list(board)}
                resolved.append({**hit, "company": hit["company"] if hit["ats"] == "greenhouse" else co,
                                 "source": source, "h1b": l["h1b"], "lead_url": l["lead_url"]})
                if board[1] not in boards[board[0]]:
                    boards[board[0]].append(board[1])
            else:
                unresolved.append(l)
        if co not in cache or not cache[co].get("board"):
            cache[co] = {"miss": today.isoformat()}
    json.dump(cache, open(cache_p, "w"), indent=1)
    A.save_boards(boards)
    return resolved, unresolved


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    days = float(argv[0]) if argv else 1
    leads = pull(days)
    resolved, unresolved = resolve(leads)
    # posted date from the ATS can be older than the newgrad listing; keep anything the lead says is fresh
    fresh, dropped = filter_jobs([{**j, "posted": j.get("posted") or datetime.now(timezone.utc).isoformat()} for j in resolved], 3650)
    q = merge_queue(fresh)
    json.dump(unresolved, open(os.path.join(WORKSPACE, "leads.json"), "w"), indent=1)
    for r in fresh:
        print(f"{r['id']} | {r['ats'][:2]} | h1b={r.get('h1b')} | {r['company'][:22]} | {r['title'][:60]} | {r['location'][:30]}")
    print(f"{len(leads)} leads: {len(fresh)} resolved to an ATS -> queue.json ({len(q)} total), "
          f"{len(unresolved)} unresolved -> leads.json; dropped {dropped}")


if __name__ == "__main__":
    main()
