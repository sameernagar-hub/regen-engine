"""Quick start / Test drive for a stranger: the roles a resume actually fits, ranked the way an ATS reads them.

    python -m engine try resume.pdf|resume.txt [--boards N] [--days D]

1. Read the resume like a recruiter: its role lane(s) (software, AI/ML, data, DevOps, security, product, design,
   program, solutions), years of experience and level, and its keywords (the engine's JD vocabulary,
   engine/tailoring/keywords.TECH, plus the product / design / analytics terms in DOMAIN below).
2. Scan a sample of public Greenhouse boards (engine/discovery/boards.example.txt) and keep only postings in those lanes,
   at a level the resume supports, in the US, posted in the last D days.
3. Fetch the job description of the best-looking shortlist and score each like an ATS: the share of the JD's keywords the
   resume also has, the experience the JD asks for against the resume's years, and freshness.
Prints the 10 best with matched and missing keywords. Read-only: no files, no events, nothing applied. Standard library
only (a PDF needs pypdf). The public site runs the same rules (apps/web/lib/tryit.ts, from scripts/try_rules.py).
"""
import collections, concurrent.futures as cf, datetime, html, json, os, re, sys, time, urllib.request

# Role lanes come from the resume classifier (engine/resume_nlp.py): tokenize, normalize, sections, longest-first
# phrases, TF-IDF-style family scores blended with nearest-centroid cosine. It labels the resume AND each posting
# title from one taxonomy of role families, so the gate compares like with like.
from engine import resume_nlp as NLP

# Product / design / analytics terms the tech vocabulary lacks, as name -> extra patterns (the name itself also matches).
DOMAIN = {
    "Product Strategy": [], "Roadmapping": [r"roadmap"], "Go-to-Market": [r"\bgtm\b"], "User Research": [r"user interviews?|customer discovery|customer research"],
    "PRDs": [r"\bprds?\b|product requirements"], "OKRs": [r"\bokrs?\b"], "Pricing": [], "Stakeholder Management": [r"stakeholders?"],
    "Cross-functional": [r"cross functional"], "Funnel Optimization": [r"funnels?"], "Retention": [r"churn"], "Growth": [],
    "Product Analytics": [r"analytics"], "Mixpanel": [], "Amplitude": [], "Jira": [], "Figma": [], "Confluence": [], "Salesforce": [],
    "Tableau": [], "Looker": [], "Excel": [], "B2B": [], "SaaS": [], "Payments": [r"payment|checkout"],
    "Enterprise": [], "Wireframing": [r"wirefram"], "Prototyping": [r"prototyp"],
    "Design Systems": [r"design system"], "Usability Testing": [r"usability"], "Accessibility": [r"wcag|a11y"], "Interaction Design": [],
    "Customer Success": [], "Technical Program Management": [r"program management"], "Risk Management": [],
    # sales / marketing (11-18), so a go-to-market resume scores on its own vocabulary
    "MEDDIC": [r"meddpicc"], "Challenger Sale": [r"challenger"], "Sandler": [], "Negotiation": [r"negotiat"],
    "Prospecting": [r"outbound"], "Pipeline Management": [r"pipeline generation|qualified pipeline"], "Quota Attainment": [r"\bquota\b"],
    "Full-Cycle Sales": [r"full.cycle sales"], "Enterprise Sales": [r"enterprise (?:sales|deals|accounts)"],
    "CRM": [r"\bcrm\b"], "HubSpot": [], "Gong": [], "ZoomInfo": [], "LinkedIn Sales Navigator": [r"sales navigator"],
    "Upselling": [r"upsell|cross.?sell|account expansion"], "Demand Generation": [r"demand gen"], "SEO": [], "Email Marketing": [],
}
# Title words that need the same word (or a sibling) on the resume, so a web resume is not sent to iOS or FPGA roles.
SPECIALTY = {"ios": r"\bios\b|swift", "android": r"android|kotlin", "mobile": r"mobile|ios|android|react native|flutter",
             "embedded": r"embedded|firmware|rtos", "firmware": r"firmware|embedded", "hardware": r"hardware|fpga|asic|pcb",
             "fpga": r"fpga|verilog", "asic": r"asic|verilog", "verification": r"verification|uvm", "salesforce": r"salesforce",
             "sap": r"\bsap\b", "mainframe": r"mainframe|cobol", "game": r"game|unity|unreal", "graphics": r"graphics|opengl|vulkan|shader",
             "robotics": r"robotics|\bros\b", "quant": r"quant|trading", "compiler": r"compiler|llvm", "kernel": r"kernel|linux internals"}
STUDENT = r"\bstudent\b|expected (?:graduation|20\d\d)|graduating|class of 20\d\d|seeking (?:an )?internship"
LEVELS = [  # (title pattern, rule) checked in order; the first that matches decides
    (r"\bintern\b|internship|co-?op\b|apprentice", "student"),
    (r"\bvp\b|vice president|\bchief\b|\bhead of\b|\bdirector\b", "exec"),
    (r"\bstaff\b|\bprincipal\b|\bdistinguished\b|\barchitect\b", "staff"),
    (r"(?<!product )(?<!program )(?<!project )\bmanager\b", "people"),
    (r"\blead\b|\bsenior\b|\bsr\.?\b|\biii\b|\biv\b|\blevel [45]\b", "senior"),
    (r"new grad|entry.level|junior|\bjr\.?\b|associate|early career|graduate|\bi\b$|\bl[1-3]\b", "junior"),
]
WEIGHTS = {"ats": 0.7, "fresh": 0.15, "lane": 0.15}
# a JD's closing boilerplate (benefits, pay, EEO) is not what the role asks for; "Go" is not the go in go-to-market
BOILERPLATE = r"\b(?:benefits (?:include|we offer)|what we offer|our benefits|perks|pay transparency|salary range|compensation range|base pay range|the (?:annual|base) salary|equal (?:employment )?opportunity|we are an equal|eeo statement)"
OVERRIDE = {"Go": [r"(?<![a-z0-9+#.])go(?![a-z0-9+#-])", r"golang"],
            # 11-18 (sales resume): "C-level", "SQL quota" (sales-qualified leads), "multi-threading complex accounts"
            "C": [r"(?<![a-z0-9+#.])c(?![a-z0-9+#-])(?! suite)", r"\bc(?= programming| language|/c\+\+|,)"],
            "SQL": [r"(?<![a-z0-9+#.])sql(?![a-z0-9+#])(?! quota| attainment| target| conversion| pipeline)"],
            "Concurrency": [r"(?<![a-z0-9+#.])concurrency(?![a-z0-9+#])", r"multi-?thread(?:ed|ing)?(?![a-z])(?! (?:complex )?(?:accounts|deals|stakeholders|buying))"]}


def resume_text(path):
    if path.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            sys.exit("Reading a PDF needs pypdf (pip install pypdf), or pass the resume as a .txt / .md file.")
        return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    return open(path, encoding="utf-8", errors="replace").read()


def plain(text):
    return " ".join(re.sub(r"<[^>]+>", " ", html.unescape(html.unescape(text or ""))).split()).lower()


def terms_table():
    """name -> compiled pattern, for every keyword the engine knows (tech + DOMAIN). Same shape as keywords._RX."""
    from engine.tailoring.keywords import TECH
    out = {}
    for name, extra in {**TECH, **DOMAIN}.items():
        pats = OVERRIDE.get(name) or [r"(?<![a-z0-9+#.])" + re.escape(name.lower()) + r"(?![a-z0-9+#])"] + list(extra)
        out[name] = re.compile("|".join(f"(?:{p})" for p in pats))
    return out


def keywords(text, table=None):
    low = plain(text)
    table = table or terms_table()
    return {name for name, rx in table.items() if rx.search(low)}


def years(text):
    """Years of experience the resume shows: an explicit "N+ years", else the span of its dated roles."""
    low = text.lower()
    said = [int(n) for n in re.findall(r"(\d{1,2})\+?\s*(?:years|yrs)", low) if int(n) < 40]
    if said:
        return max(said)
    now = datetime.date.today().year
    spans = re.findall(r"((?:19|20)\d\d)\s*(?:-|–|—|to)\s*((?:19|20)\d\d|present|current|now)", low)
    starts = [int(a) for a, _ in spans]
    return max(0, now - min(starts)) if starts else 0


def profile(text, table=None):
    """What a recruiter reads first: lanes (strongest first), years, whether it reads senior / student, keywords."""
    low = plain(text)
    a = NLP.analyze(text)
    lanes = a["labels"]  # [] = unclassified: nothing is guessed, every posting is filtered with that reason
    y = years(text)
    return {"lanes": lanes, "analysis": a, "years": y, "senior": y >= 5 or bool(re.search(r"\bsenior\b|\bsr\.?\s", low)),
            "student": bool(re.search(STUDENT, low)), "keywords": sorted(keywords(text, table)),
            "staff": y >= 8 or bool(re.search(r"\bstaff\b|\bprincipal\b", low)),
            "people": bool(re.search(r"engineering manager|managed a team of|direct reports", low)), "low": low}


def level_ok(title, p):
    """None when the resume supports the posting's level, else the reason."""
    t = title.lower()
    for pat, rule in LEVELS:
        if re.search(pat, t):
            if rule == "student":
                return None if p["student"] else "internship (resume is not a student's)"
            if rule == "exec":
                return "executive level" if p["years"] < 12 else None
            if rule == "staff":
                return None if p["staff"] else "staff / principal level"
            if rule == "people":
                return None if p["people"] else "people-manager role"
            if rule == "senior":
                return None if p["senior"] or p["years"] >= 4 else "senior level"
            if rule == "junior":
                return None if p["years"] <= 3 or "associate" in t and "product" in t and p["years"] <= 5 else "junior level"
    return None


def gate(job, p, now, days):
    """None when the posting fits the resume's profile, else the reason it was filtered (same keys the page charts)."""
    from engine.discovery.filters import DEFAULT_DOMAIN, us_location, NON_US, US_WORDS
    title, loc = job.get("title", ""), job.get("location", "")
    if not p["lanes"]:
        return "resume not classified"
    fams = NLP.classify_title(title)
    if not fams:
        return "title not recognized"
    if not set(fams) & set(p["lanes"]):
        return "different kind of role"
    why = level_ok(title, p)
    if why:
        return "level: " + why
    for word, need in SPECIALTY.items():
        if re.search(r"\b" + word + r"\b", title, re.I) and not re.search(need, p["low"]):
            return "specialty the resume doesn't show"
    co = job.get("company", "")
    rx = re.compile(DEFAULT_DOMAIN["exclude_companies"], re.I)
    if co and (rx.search(co) or rx.search(re.sub(r"[\s_-]+", " ", co))):
        return "company excluded (clearance / defense)"
    if not us_location(loc) or (NON_US.search(title) and not US_WORDS.search(title)):
        return "outside the US"
    age = age_days(job, now)
    if age is not None and age > days:
        return f"older than {days} days"
    return None


def age_days(job, now):
    try:
        return (now - datetime.datetime.fromisoformat((job.get("posted") or "").replace("Z", "+00:00"))).days
    except ValueError:
        return None


def jd_years(jd_low):
    """The experience a JD asks for (the smallest "N+ years" it states), or None."""
    asks = [int(n) for n in re.findall(r"(\d{1,2})\+?\s*(?:or more\s*)?(?:years|yrs)", jd_low) if 0 < int(n) < 20]
    return min(asks) if asks else None


def role_text(jd):
    """The JD without its closing boilerplate (cut only in the back 40%, so an early 'benefits' mention keeps the rest)."""
    low = plain(jd)
    m = re.search(BOILERPLATE, low[int(len(low) * 0.6):])
    return low[:int(len(low) * 0.6) + m.start()] if m else low


def score(job, jd, p, table, now):
    """ATS-style: (score, matched, missing, asks_years). JD keywords the resume shares (a short JD counts for less),
    freshness, lane fit; a JD that asks for more years than the resume shows, or a senior title on < 5 years, costs."""
    jd_low = role_text(jd)
    co = re.sub(r"[^a-z0-9]", "", (job.get("company") or "").lower())
    want = {name for name, rx in table.items() if rx.search(jd_low) and re.sub(r"[^a-z0-9]", "", name.lower()) != co} \
        or keywords(job.get("title", ""), table)
    have = set(p["keywords"])
    matched, missing = sorted(want & have), sorted(want - have)
    ats = (len(matched) / len(want)) * (0.6 + 0.4 * min(1, len(want) / 10)) if want else 0.0
    age = age_days(job, now)
    fresh = 1.0 if age is None else max(0.0, 1 - age / 30)
    lane = 1.0 if p["lanes"] and p["lanes"][0] in NLP.classify_title(job.get("title", "")) else 0.6
    asks = jd_years(jd_low)
    s = WEIGHTS["ats"] * ats + WEIGHTS["fresh"] * fresh + WEIGHTS["lane"] * lane
    if asks is not None and asks > p["years"] + 1:
        s -= 0.15 * min(3, asks - p["years"] - 1)
    if re.search(r"\bsenior\b|\bsr\.?\b", job.get("title", ""), re.I) and p["years"] < 5:
        s -= 0.08
    return s, matched, missing, asks


def reason(match_pct, matched, missing, asks, p, age):
    r = f"ATS match {match_pct}% ({len(matched)} of {len(matched) + len(missing)} JD keywords)"
    if matched:
        r += ": " + ", ".join(matched[:6])
    if missing:
        r += "; missing " + ", ".join(missing[:4])
    if asks is not None:
        r += f"; asks {asks}+ yrs, resume shows {p['years']}"
    if age is not None:
        r += f"; posted {age} d ago"
    return r


def shortlist(jobs, p, now, days, n=36, per_company=3):
    """(candidates, blocked Counter): postings past the gate, best-looking first by title keywords + freshness."""
    blocked, cand = collections.Counter(), []
    have = set(p["keywords"])
    table = None
    for j in jobs:
        why = gate(j, p, now, days)
        if why:
            blocked[why] += 1
            continue
        table = table or terms_table()
        tk = keywords(j.get("title", ""), table)
        age = age_days(j, now)
        pre = len(tk & have) - 0.5 * len(tk - have) + (1 if age is not None and age <= 7 else 0)
        cand.append((pre, j.get("posted") or "", j))
    cand.sort(key=lambda x: (x[0], x[1]), reverse=True)
    out, per = [], collections.Counter()
    for _, _, j in cand:
        if per[j.get("company")] < per_company:
            out.append(j)
            per[j.get("company")] += 1
        if len(out) >= n:
            break
    return out, blocked, len(cand)


def greenhouse_jd(job):
    """The posting's description HTML from the public board API ('' when it fails)."""
    m = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", job.get("url", ""))
    if not m:
        return ""
    try:
        req = urllib.request.Request(f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}",
                                     headers={"User-Agent": "regen-engine try"})
        return json.load(urllib.request.urlopen(req, timeout=15)).get("content", "")
    except Exception:
        return ""


def rank(jobs, text, now=None, days=30, fetch=None, top=10):
    """Everything the CLI and the API need: profile, ranked top roles with reasons, what the gate filtered."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    fetch = fetch or greenhouse_jd
    table = terms_table()
    p = profile(text, table)
    cands, blocked, passing = shortlist(jobs, p, now, days)
    with cf.ThreadPoolExecutor(12) as ex:
        jds = list(ex.map(fetch, cands))
    ranked = []
    for j, jd in zip(cands, jds):
        s, matched, missing, asks = score(j, jd, p, table, now)
        pct = round(100 * len(matched) / max(1, len(matched) + len(missing)))
        ranked.append((s, j, reason(pct, matched, missing, asks, p, age_days(j, now)), pct, matched, missing))
    ranked.sort(key=lambda x: x[0], reverse=True)
    per, seen, best = collections.Counter(), set(), []
    for r in ranked:  # at most two roles per company in the top 10, and one per title (multi-city reposts)
        key = (r[1].get("company"), r[1].get("title"))
        if key in seen:
            continue
        seen.add(key)
        if per[r[1].get("company")] < 2:
            best.append(r)
            per[r[1].get("company")] += 1
        if len(best) >= top:
            break
    prof = {k: p[k] for k in ("lanes", "years", "senior", "student", "keywords")}
    return {"profile": prof, "analysis": p["analysis"], "passing": passing, "blocked": dict(blocked.most_common()), "checked": len(cands),
            "top": [{"company": j.get("company"), "title": j.get("title"), "location": j.get("location"), "url": j.get("url"),
                     "reason": why, "match": pct, "matched": m, "missing": mi} for _, j, why, pct, m, mi in best]}


def sample_boards(n):
    p = os.path.join(os.path.dirname(__file__), "discovery", "boards.example.txt")
    return [t.strip() for t in open(p, encoding="utf-8").read().split(",") if t.strip()][:n]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0].startswith("-"):
        sys.exit("usage: python -m engine try resume.pdf|resume.txt [--boards N] [--days D]")
    opt = lambda k, d: int(argv[argv.index(k) + 1]) if k in argv and argv.index(k) + 1 < len(argv) else d
    t0 = time.time()
    text = resume_text(argv[0])
    from engine.discovery.ats import fetch_all
    boards = sample_boards(opt("--boards", 40))
    jobs, _, total = fetch_all({"greenhouse": boards}, workers=16)
    out = rank(jobs, text, days=opt("--days", 30))
    p, a = out["profile"], out["analysis"]
    st = a["steps"]
    print(f"Pipeline: {st['tokens']} tokens -> {st['terms']} normalized terms ({st['stopwords']} stopwords dropped, "
          f"{st['aliases']} abbreviations expanded) -> sections {', '.join(st['sections']) or 'none found'}, {st['roles']} roles "
          f"-> {st['phrases']} matched phrases")
    print("Classifier: " + ", ".join(f"{s['family']} {s['p']:.0%}" for s in st["scores"][:4]) +
          f"  (confidence {a['level']}{', hybrid profile' if a['hybrid'] else ''})")
    if not p["lanes"]:
        print("The resume could not be classified: too little evidence of any kind of role. Add your job titles and skills.")
    print(f"Your resume reads as: {', '.join(p['lanes']) or 'unclassified'} · {p['years']} yrs{' · senior' if p['senior'] else ''}"
          f"{' · student' if p['student'] else ''} · {len(p['keywords'])} keywords ({', '.join(p['keywords'][:12])}{'…' if len(p['keywords']) > 12 else ''})")
    print(f"\nScanned {len(boards)} public boards, {total} postings; {out['passing']} fit your profile; read {out['checked']} job descriptions.\n"
          f"Top {len(out['top'])} by ATS match:\n")
    for i, j in enumerate(out["top"], 1):
        print(f"{i:>2}. {j['company']}: {j['title']}  [{j.get('location') or '-'}]\n    {j['reason']}\n    {j['url']}")
    print("\nFiltered out: " + (", ".join(f"{n} {r}" for r, n in out["blocked"].items()) or "none"))
    print(f"Done in {time.time() - t0:.0f} s. Nothing was applied to and nothing was saved. "
          "For illustration only: check each posting yourself before you apply.")


if __name__ == "__main__":
    main()
