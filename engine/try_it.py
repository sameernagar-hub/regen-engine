"""Quick start for a stranger: a first result in minutes with no database, no Docker and nothing applied.

    python -m engine try resume.pdf|resume.txt [--boards N] [--days D]

Reads the resume (PDF needs the one optional dependency, pypdf; .txt / .md need nothing), scans a sample of public
Greenhouse boards (engine/discovery/boards.example.txt), runs the same fit gate the engine uses (default rules, not
anyone's profile), and prints the 10 best-fitting fresh roles with the reason each passed, plus why the rest were
blocked. Read-only: it writes no files and records no events. Standard library only, apart from pypdf for PDFs.
O(B) board fetches in parallel, then O(J) over the postings.
"""
import collections, datetime, os, re, sys, time

# Role families: a title word and the resume words that show the same skill. A title earns points only for families
# the resume also shows, so a ranking never claims a skill the resume lacks.
FAMILIES = {
    "ai / ml": (r"\bai\b|machine learning|\bml\b|\bllm|applied ai|genai|deep learning",
                r"machine learning|\bml\b|pytorch|tensorflow|\bllm|langchain|transformers?|\bnlp\b|computer vision|\bai\b"),
    "backend": (r"back.?end|platform|infrastructure|distributed|api\b|server",
                r"back.?end|rest\b|api|postgres|sql|django|flask|fastapi|node|spring|\bgo\b|golang|microservice|kafka|redis"),
    "full stack": (r"full.?stack|product engineer|founding", r"react|next\.?js|typescript|javascript|node|full.?stack"),
    "frontend": (r"front.?end|\bui\b|web", r"react|vue|angular|typescript|javascript|css|html|front.?end"),
    "data": (r"\bdata\b|analytics|etl|pipeline", r"\bsql\b|spark|airflow|dbt|pandas|etl|data pipeline|snowflake|bigquery"),
    "cloud / devops": (r"devops|\bsre\b|reliability|cloud|kubernetes",
                       r"aws|gcp|azure|docker|kubernetes|terraform|ci/cd|devops|linux"),
    "forward deployed": (r"forward.?deployed|solutions engineer", r"customer|client|deploy|integration|consult"),
}


def resume_text(path):
    if path.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            sys.exit("Reading a PDF needs pypdf (pip install pypdf), or pass the resume as a .txt / .md file.")
        return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    return open(path, encoding="utf-8", errors="replace").read()


def skills(text):
    """Families the resume shows, each with the words that showed it."""
    out = {}
    for fam, (_, words) in FAMILIES.items():
        hits = sorted({m.group(0).lower() for m in re.finditer(words, text, re.I)})
        if hits:
            out[fam] = hits
    return out


def sample_boards(n):
    p = os.path.join(os.path.dirname(__file__), "discovery", "boards.example.txt")
    return [t.strip() for t in open(p, encoding="utf-8").read().split(",") if t.strip()][:n]


def domain():
    """The engine's default fit-gate rules, compiled; a stranger's run never reads the owner's profile."""
    from engine.discovery.filters import DEFAULT_DOMAIN
    return {k: re.compile(v, re.I) if isinstance(v, str) else v for k, v in DEFAULT_DOMAIN.items()}


def rank(jobs, have, now=None, days=14):
    """(passed, blocked): passed = [(score, job, reason)] best first; blocked = Counter of gate reasons."""
    from engine.discovery.filters import keep
    now = now or datetime.datetime.now(datetime.timezone.utc)
    dom, passed, blocked = domain(), [], collections.Counter()
    for j in jobs:
        why = keep(dom, j.get("title", ""), j.get("location", ""), j.get("company", ""))
        age = None
        try:
            age = (now - datetime.datetime.fromisoformat((j.get("posted") or "").replace("Z", "+00:00"))).days
        except ValueError:
            pass
        if why is None and age is not None and age > days:
            why = f"older than {days} days"
        fams = [f for f, (title_words, _) in FAMILIES.items() if re.search(title_words, j.get("title", ""), re.I)]
        match = [f for f in fams if f in have]
        if why is None and fams and not match:
            why = "resume does not show this role's skills"
        if why:
            blocked[why] += 1
            continue
        score = 2 * len(match) + (1 if age is not None and age <= 3 else 0)
        reason = ("matches " + "; ".join(f"{f} ({', '.join(have[f][:3])})" for f in match) if match
                  else "passes the gate (general software title)")
        reason += f"; posted {age} d ago" if age is not None else ""
        passed.append((score, j, reason))
    passed.sort(key=lambda x: (x[0], x[1].get("posted") or ""), reverse=True)  # best, then newest
    return passed, blocked


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0].startswith("-"):
        sys.exit("usage: python -m engine try resume.pdf|resume.txt [--boards N] [--days D]")
    opt = lambda k, d: int(argv[argv.index(k) + 1]) if k in argv and argv.index(k) + 1 < len(argv) else d
    t0 = time.time()
    have = skills(resume_text(argv[0]))
    print("Your resume shows: " + ("; ".join(f"{f} ({', '.join(w[:4])})" for f, w in have.items()) or "no known skill words"))
    from engine.discovery.ats import fetch_all
    boards = sample_boards(opt("--boards", 40))
    jobs, _, total = fetch_all({"greenhouse": boards}, workers=16)
    passed, blocked = rank(jobs, have, days=opt("--days", 14))
    print(f"\nScanned {len(boards)} public boards, {total} postings. Top {min(10, len(passed))} of {len(passed)} that pass:\n")
    for i, (_, j, reason) in enumerate(passed[:10], 1):
        print(f"{i:>2}. {j['company']}: {j['title']}  [{j.get('location') or '-'}]\n    {reason}\n    {j['url']}")
    print("\nBlocked by the fit gate: " + (", ".join(f"{n} {r}" for r, n in blocked.most_common()) or "none"))
    print(f"Done in {time.time() - t0:.0f} s. Nothing was applied to and nothing was saved.")


if __name__ == "__main__":
    main()
