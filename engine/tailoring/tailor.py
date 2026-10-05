"""Per-job tailoring and fit checks, still Fact-Bank-only.

tailor(lane_spec, jd) keeps the lane's shape (same number of bullets per role, same number of
projects) but picks and orders them by how many of the job's technologies they mention. Candidates
are every fact the bank holds for that role, so nothing new can appear: validate() still gates
the result.

fit(jd) reads the job description for hard blockers (citizenship, clearance, no sponsorship,
grad windows you're outside of, years of experience above your level).
"""
import re

from engine.tailoring import resume

STOP = {"and", "or", "the", "a", "of", "with", "for", "in", "to", "on", "development", "ui", "design", "systems",
        "data", "cloud", "testing", "linux", "git", "html/css", "monitoring", "alerting", "responsive"}


def vocabulary():
    """Technology terms the candidate actually has, taken from the Fact Bank skills lines."""
    resume.load_bank()
    terms = set()
    for _, line in resume.SKILLS.values():
        for t in re.split(r",|/|\(|\)|--", line):
            t = t.strip().lower()
            if 2 <= len(t) <= 40 and t not in STOP:
                terms.add(t)
    # useful single-word aliases from multi-word skills ("aws (eks" -> "aws", "eks")
    for t in list(terms):
        for w in t.split():
            if len(w) >= 3 and w not in STOP and re.fullmatch(r"[a-z0-9+#.\-]+", w):
                terms.add(w)
    return terms


def _hits(text, terms):
    low = re.sub(r"<[^>]+>", " ", text).lower()
    return {t for t in terms if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low)}


def tailor(spec, jd):
    resume.load_bank()
    terms = vocabulary()
    want = _hits(jd, terms)
    score = lambda text: len(_hits(text, want))
    by_role = {}
    for fid, text in resume.FACTS.items():
        by_role.setdefault(fid.split("_")[0], []).append(fid)
    roles = []
    for rk, fids in spec["roles"]:
        prefix = fids[0].split("_")[0] if fids else rk[0]
        pool = list(dict.fromkeys(fids + by_role.get(prefix, [])))  # lane order first, then the rest of the role
        rank = sorted(pool, key=lambda f: (-score(resume.FACTS[f]), pool.index(f)))
        roles.append([rk, rank[:len(fids)]])
    projects = spec.get("projects", [])
    if projects:
        allp = list(dict.fromkeys(projects + list(resume.PROJECTS)))
        ptxt = lambda p: " ".join([resume.PROJECTS[p][0]] + resume.PROJECTS[p][2])
        projects = sorted(allp, key=lambda p: (-score(ptxt(p)), allp.index(p)))[:len(projects)]
    skills = sorted(spec["skills"], key=lambda k: (-score(resume.SKILLS[k][1]), spec["skills"].index(k)))
    out = dict(spec, roles=roles, projects=projects, skills=skills)
    resume.validate(out)
    covered = set()
    for _, fids in roles:
        for f in fids:
            covered |= _hits(resume.FACTS[f], want)
    for k in skills:
        covered |= _hits(resume.SKILLS[k][1], want)
    out["_coverage"] = {"jd_terms_you_have": sorted(want), "on_resume": sorted(covered), "missing_from_resume": sorted(want - covered)}
    return out


BLOCKERS = [
    ("citizenship", r"u\.?s\.? citizen(ship)? (is )?(required|only)|must be (a )?u\.?s\.? citizen|requires? u\.?s\.? citizenship|us persons? only|\bitar\b|export control|green card holders? only"),
    ("clearance", r"(active|current|obtain|eligib\w+ for)( a)? (secret|ts|top secret|security) clearance|polygraph"),
    ("no sponsorship", r"(unable|not able|will not|won.t|cannot|can.t|do(es)? not|no longer)( be able to)? (to )?(provide |offer )?(visa )?sponsor|sponsorship (is )?not (available|provided|offered)|without (the need for )?(current or future )?(visa )?sponsorship|not eligible for (visa )?sponsorship"),
    ("grad window", r"(graduating|graduation date|expected to graduate|graduate) (in|between|from|during)[^.]{0,40}(2027|2028)|class of (2027|2028)|(2027|2028) (start|new grads?|graduates)"),
]


def fit(jd, max_years=4):
    """List of hard blockers found in the job description (empty = clear)."""
    low = " ".join(jd.split()).lower()
    out = [name for name, pat in BLOCKERS if re.search(pat, low)]
    # "5+ years", "4-7 years", "5 to 15+ years": the lower bound is the requirement
    yrs = [int(m.group(1)) for m in re.finditer(r"(?<![\d.])(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*\d{1,2}\s*\+?\s*)?years?(?: of)?[^.]{0,60}experience", low)]
    yrs = [y for y in yrs if y < 20]
    if yrs and min(yrs) > max_years:
        out.append(f"{min(yrs)}+ yrs")
    return out
