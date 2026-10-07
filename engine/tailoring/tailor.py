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
    for canon, alts in resume.ALIASES.items():
        if canon.lower() in terms:
            terms |= {a.lower() for a in alts}
    return terms


def _hits(text, terms):
    low = re.sub(r"<[^>]+>", " ", text).lower()
    return {t for t in terms if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low)}


def distinct(ranked, n):
    """Top n facts, never two from the same overlap group (Fact Bank "_overlaps": versions of one accomplishment)."""
    groups = [set(g) for g in resume.OVERLAPS]
    out = []
    for f in ranked:
        if len(out) == n:
            break
        if not any(f in g and any(o in g for o in out) for g in groups):
            out.append(f)
    return out


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
        roles.append([rk, distinct(rank, len(fids))])
    projects = spec.get("projects", [])
    if projects:
        allp = list(dict.fromkeys(projects + list(resume.PROJECTS)))
        ptxt = lambda p: " ".join([resume.PROJECTS[p][0]] + resume.PROJECTS[p][2])
        projects = sorted(allp, key=lambda p: (-score(ptxt(p)), allp.index(p)))[:len(projects)]
    skills = sorted(spec["skills"], key=lambda k: (-score(resume.SKILLS[k][1]), spec["skills"].index(k)))
    # one extra skills line the lane doesn't carry, when the JD clearly asks for it (e.g. Salesforce, AI dev tools)
    extra = max((k for k in resume.SKILLS if k not in skills), key=lambda k: score(resume.SKILLS[k][1]), default=None)
    if extra and score(resume.SKILLS[extra][1]) >= 2:
        skills.append(extra)
    skill_text = {k: t for k in skills if (t := resume.jd_spelling(resume.SKILLS[k][1], jd)) != resume.SKILLS[k][1]}
    out = dict(spec, roles=roles, projects=projects, skills=skills, skill_text=skill_text)
    resume.validate(out)
    covered = set()
    for _, fids in roles:
        for f in fids:
            covered |= _hits(resume.FACTS[f], want)
    for k in skills:
        covered |= _hits(skill_text.get(k, resume.SKILLS[k][1]), want)
    out["_coverage"] = {"jd_terms_you_have": sorted(want), "on_resume": sorted(covered), "missing_from_resume": sorted(want - covered)}
    return out


BLOCKERS = [
    ("citizenship", r"u\.?s\.? citizen(ship)? (is )?(required|only)|must be (a )?u\.?s\.? citizen|requires? u\.?s\.? citizenship|us persons? only|\bitar\b|export control|green card holders? only"),
    ("clearance", r"(active|current|obtain|eligib\w+ for)( a)? (secret|ts|top secret|security) clearance|polygraph"),
    ("no sponsorship", r"(unable|not able|will not|won.t|cannot|can.t|do(es)? not|no longer)( be able to)? (to )?(provide |offer )?(visa )?sponsor|sponsorship (is )?not (available|provided|offered)|without (the need for )?(current or future )?(visa )?sponsorship|not eligible for (visa )?sponsorship"),
    ("grad window", r"(graduating|graduation date|expected to graduate|graduate) (in|between|from|during)[^.]{0,40}(2027|2028)|class of (2027|2028)|(2027|2028) (start|new grads?|graduates)"),
]


# Languages/stacks a JD can make the core of the job. If the JD *requires* one ("strong C++", "proficiency in Go",
# "C# required") and the Fact Bank has no such skill, the screen rejects (seen: "Strong modern C++" -> rejected in 2 days).
CORE_STACKS = {"c++": r"c\+\+", "c#": r"c#|\.net", "java": r"java(?!script)", "go": r"golang|go(?![a-z0-9]| to| above| beyond)",
               "rust": r"rust", "scala": r"scala", "kotlin": r"kotlin", "swift": r"swift|ios", "ruby": r"ruby|rails",
               "php": r"php", "embedded": r"embedded|firmware|rtos", "verilog": r"verilog|vhdl|fpga"}
REQUIRED_CUE = r"(strong|deep|expert|extensive|solid|proficien\w*|fluen\w*|mastery|advanced|professional|production)[^.;]{0,40}(?:{s})|(?:{s})[^.;]{0,25}(required|must|is a must|proficiency|expertise|experience required)"


def user_years():
    """Years of experience from the presets (the number the forms are answered with)."""
    try:
        from engine.apply.runner import P
        return int(P.get("years_experience") or 99)
    except Exception:
        return 99


def fit(jd, max_years=None):
    """List of hard blockers found in the job description (empty = clear)."""
    max_years = user_years() if max_years is None else max_years
    low = " ".join(re.sub(r"<[^>]+>", " ", jd).split()).lower()
    out = [name for name, pat in BLOCKERS if re.search(pat, low)]
    have = vocabulary()
    for name, s in CORE_STACKS.items():
        if not any(re.fullmatch(s, t) or re.search(r"(?<![a-z0-9])" + s + r"(?![a-z0-9])", t) for t in have)                 and re.search(REQUIRED_CUE.replace("{s}", s), low):
            out.append(f"core stack: {name}")
    # "5+ years", "4-7 years", "5 to 15+ years": the lower bound is the requirement
    yrs = [int(m.group(1)) for m in re.finditer(r"(?<![\d.])(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*\d{1,2}\s*\+?\s*)?years?(?: of)?[^.]{0,60}experience", low)]
    yrs = [y for y in yrs if y < 20]
    if yrs and min(yrs) > max_years:
        out.append(f"{min(yrs)}+ yrs")
    return out
