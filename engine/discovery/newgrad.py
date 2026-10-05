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
    c = {"".join(words), "".join(core), "-".join(core), "".join(core[:1]), "".join(core[:2])}
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


def resolve(leads):
    """Find each lead on its employer's own ATS board."""
    cache_p = os.path.join(WORKSPACE, "resolve_cache.json")
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
    boards = A.load_boards()
    # company -> candidate boards: cached, already-registered boards with a matching slug, then guesses
    companies = sorted({l["company"] for l in leads})

    def candidates(co):
        if co in cache:
            return [tuple(cache[co])] if cache[co] else []
        out = []
        for s in slugs(co):
            for a in A.ATS:
                out.append((a, s))
        return out

    def board_jobs(at):
        try:
            return at, A.FETCH[at[0]](at[1])
        except Exception:
            return at, None

    todo = {at for co in companies for at in candidates(co)}
    fetched = {}
    with cf.ThreadPoolExecutor(32) as ex:
        for at, jobs in ex.map(board_jobs, todo):
            fetched[at] = jobs
    resolved, unresolved = [], []
    for co in companies:
        cands = [at for at in candidates(co) if fetched.get(at)]
        if co not in cache:
            # prefer the board whose jobs mention the most of this company's lead titles
            mine = [norm(l["title"]) for l in leads if l["company"] == co]
            score = lambda at: sum(1 for j in fetched[at] if norm(j["title"]) in mine)
            best = max(cands, key=score, default=None)
            cache[co] = list(best) if best and score(best) else (list(best) if best and len(cands) == 1 else None)
        board = tuple(cache[co]) if cache[co] else None
        for l in (x for x in leads if x["company"] == co):
            hit = None
            if board and fetched.get(board):
                titles = {j["id"]: norm(j["title"]) for j in fetched[board]}
                want = norm(l["title"])
                exact = [j for j in fetched[board] if titles[j["id"]] == want]
                fuzzy = [j for j in fetched[board] if difflib.SequenceMatcher(None, titles[j["id"]], want).ratio() >= 0.88]
                pool = exact or fuzzy
                if pool:
                    hit = max(pool, key=lambda j: j.get("posted") or "")
            if hit:
                resolved.append({**hit, "company": l["company"] if hit["ats"] != "greenhouse" else hit["company"],
                                 "source": "newgrad-jobs", "h1b": l["h1b"], "lead_url": l["lead_url"]})
                if board[1] not in boards[board[0]]:
                    boards[board[0]].append(board[1])
            else:
                unresolved.append(l)
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
