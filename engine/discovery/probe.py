"""Find the job boards of employers you care about that the registry doesn't know yet.

    python -m engine boards probe          (names come from profile/priority.json tier lists)

For each employer name, try a few slug spellings on the three public ATS APIs and keep the ones that answer with
jobs. One small GET per (slug, ATS), run in threads; known boards are skipped, so a second run costs almost nothing.
O(N x S x 3) requests for N names and S spellings (S <= 3).
"""
import concurrent.futures as cf, json, re, urllib.request

from engine.discovery.ats import load_boards, save_boards

URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{}/jobs",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{}",
    "lever": "https://api.lever.co/v0/postings/{}?limit=1&mode=json",
}


def names():
    """Employer names from the tier regexes (alternations), without regex syntax."""
    from engine.config import profile_file
    raw = json.load(open(profile_file("priority.json"), encoding="utf-8"))
    out = set()
    for k in ("tier1", "tier2", "sponsors"):
        for alt in (raw.get(k) or "").split("|"):
            n = re.sub(r"\\b|[\\^$()?*+]|\s\?", "", alt).replace(" ?", " ").strip()
            if n:
                out.add(n)
    return sorted(out)


def slugs(name):
    """'scale ai' -> ['scaleai', 'scale-ai']."""
    w = re.findall(r"[a-z0-9]+", name.lower())
    return list(dict.fromkeys(["".join(w), "-".join(w)] if w else []))  # no first-word guess: it matched unrelated boards


def _has_jobs(ats, slug):
    try:
        req = urllib.request.Request(URLS[ats].format(slug), headers={"User-Agent": "regen-engine board probe"})
        data = json.load(urllib.request.urlopen(req, timeout=10))
    except Exception:  # 404 / timeout / bad JSON all mean "no board here"
        return False
    jobs = data.get("jobs") if isinstance(data, dict) else data
    return bool(jobs)


def probe():
    b = load_boards()
    known = {a: {s.lower() for s in b.get(a, [])} for a in URLS}
    tasks = [(a, s) for n in names() for s in slugs(n) for a in URLS if s not in known[a]]
    found = []
    with cf.ThreadPoolExecutor(16) as ex:
        for (a, s), ok in zip(tasks, ex.map(lambda t: _has_jobs(*t), tasks)):
            if ok:
                found.append((a, s))
                b.setdefault(a, []).append(s)
    save_boards(b)
    return found, len(tasks)


def main(argv=None):
    found, n = probe()
    for a, s in found:
        print(f"  + {a}: {s}")
    print(f"probed {n} slug/ATS pairs, {len(found)} new boards added to boards.json")


if __name__ == "__main__":
    main()
