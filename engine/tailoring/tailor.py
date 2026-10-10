"""Per-job tailoring and fit checks, still Fact-Bank-only.

tailor(lane_spec, jd) keeps the lane's shape (same number of bullets per role, same number of
projects) but picks and orders them by how many of the job's technologies they mention. Candidates
are every fact the bank holds for that role, so nothing new can appear: validate() still gates
the result.

fit(jd) reads the job description for hard blockers (citizenship, clearance, no sponsorship,
grad windows you're outside of, years of experience above your level).

Complexity (v0.8). T = vocabulary terms (~200), F = Fact Bank entries, n = JD length, k = facts in a pool.
  vocabulary()   built once per loaded Fact Bank and cached: O(1) after the first call (was rebuilt on every call)
  _hits(text)    one compiled boundary regex per term, cached; a C-speed `term in text` substring test runs first
                 and the regex only confirms the word boundary. Same O(T*n) bound, but most terms are rejected
                 by one memchr-style scan instead of a regex compile-cache lookup plus a full regex scan
  tailor()       each fact / project / skills text is matched once per JD (memo), then scoring is len(set);
                 ordering uses precomputed positions instead of list.index inside the sort key
                 (O(k^2 log k) -> O(k log k)); distinct() maps fact -> overlap groups in a dict: O(k)
  fit()          blocker and stack patterns compiled once; "does the Fact Bank have stack X" is computed once
                 per vocabulary instead of once per JD
"""
import html
import re

from engine.tailoring import compose, resume

STOP = {"and", "or", "the", "a", "of", "with", "for", "in", "to", "on", "development", "ui", "design", "systems",
        "data", "cloud", "testing", "linux", "git", "html/css", "monitoring", "alerting", "responsive"}


_VOCAB = {"key": None, "terms": frozenset()}
_PAT = {}


def _pat(t):
    p = _PAT.get(t)
    if p is None:
        p = _PAT[t] = re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])")
    return p


def vocabulary():
    """Technology terms the candidate actually has, taken from the Fact Bank skills lines (cached per bank)."""
    resume.load_bank()
    if _VOCAB["key"] is resume.SKILLS:
        return _VOCAB["terms"]
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
    _VOCAB.update(key=resume.SKILLS, terms=frozenset(terms))
    return _VOCAB["terms"]


def _hits(text, terms):
    low = re.sub(r"<[^>]+>", " ", text).lower()
    return {t for t in terms if t in low and _pat(t).search(low)}  # substring prefilter, then the boundary check


def distinct(ranked, n):
    """Top n facts, never two from the same overlap group (Fact Bank "_overlaps": versions of one accomplishment)."""
    group_of = {}
    for i, g in enumerate(resume.OVERLAPS):
        for f in g:
            group_of.setdefault(f, set()).add(i)
    out, used = [], set()
    for f in ranked:
        if len(out) == n:
            break
        gs = group_of.get(f, ())
        if not used.intersection(gs):
            out.append(f)
            used.update(gs)
    return out


def tailor(spec, jd, title=None, lanes=None):
    resume.load_bank()
    terms = vocabulary()
    want = _hits(jd, terms)
    memo = {}

    def hits(text):  # each fact / project / skills text is matched once per JD
        h = memo.get(text)
        if h is None:
            h = memo[text] = _hits(text, want)
        return h
    score = lambda text: len(hits(text))
    by_role = {}
    for fid, text in resume.FACTS.items():
        by_role.setdefault(fid.split("_")[0], []).append(fid)
    roles = []
    for rk, fids in spec["roles"]:
        prefix = fids[0].split("_")[0] if fids else rk[0]
        pool = list(dict.fromkeys(fids + by_role.get(prefix, [])))  # lane order first, then the rest of the role
        pos = {f: i for i, f in enumerate(pool)}
        rank = sorted(pool, key=lambda f: (-score(resume.FACTS[f]), pos[f]))
        roles.append([rk, distinct(rank, len(fids))])
    projects = spec.get("projects", [])
    if projects:
        allp = list(dict.fromkeys(projects + list(resume.PROJECTS)))
        ptxt = lambda p: " ".join([resume.PROJECTS[p][0]] + resume.PROJECTS[p][2])
        ppos = {p: i for i, p in enumerate(allp)}
        projects = sorted(allp, key=lambda p: (-score(ptxt(p)), ppos[p]))[:len(projects)]
    spos = {k: i for i, k in enumerate(spec["skills"])}
    skills = sorted(spec["skills"], key=lambda k: (-score(resume.SKILLS[k][1]), spos[k]))
    # one extra skills line the lane doesn't carry, when the JD clearly asks for it (e.g. Salesforce, AI dev tools)
    extra = max((k for k in resume.SKILLS if k not in skills), key=lambda k: score(resume.SKILLS[k][1]), default=None)
    if extra and score(resume.SKILLS[extra][1]) >= 2:
        skills.append(extra)
    # v0.9 JD-first composition: each skills line leads with the posting's terms, in the posting's spelling
    skill_text = {k: t for k in skills
                  if (t := resume.jd_spelling(compose.order_skill_line(resume.SKILLS[k][1], want), jd)) != resume.SKILLS[k][1]}
    out = dict(spec, roles=roles, projects=projects, skills=skills, skill_text=skill_text)
    if title is not None:  # headline names the role + the posting's top terms; summary leads with what answers it
        out["headline"] = compose.headline(title, jd, want, resume.SKILLS, spec["headline"])
        out["summary"] = compose.summary(jd, spec, lanes or {}, hits)
    out.pop("projects_title", None) if not projects else None
    resume.validate(out)
    covered = set()
    for _, fids in roles:
        for f in fids:
            covered |= hits(resume.FACTS[f])
    for k in skills:
        covered |= hits(skill_text.get(k, resume.SKILLS[k][1]))
    out["_coverage"] = {"jd_terms_you_have": sorted(want), "on_resume": sorted(covered), "missing_from_resume": sorted(want - covered)}
    return out


BLOCKERS = [
    ("citizenship", r"u\.?s\.? citizen(ship)? (is )?(required|only)|must be (a )?u\.?s\.? citizen|requires? u\.?s\.? citizenship|us persons? only|\bitar\b|export control|green card holders? only"),
    ("clearance", r"(active|current|obtain|eligib\w+ for)( a)? (secret|ts|top secret|security) clearance|polygraph"),
    ("defense", r"department of (defense|war)|\bdod\b|warfighters?|national security (mission|customers)|defense (tech|technology|industry|customers|sector)|military (customers|operations|end users)"),  # 10-09: defense employers got through on slug spelling
    ("no sponsorship", r"(unable|not able|will not|won.t|cannot|can.t|do(es)? not|no longer)( be able to)? (to )?(provide |offer )?(visa )?sponsor|sponsorship (is )?not (available|provided|offered)|without (the need for )?(current or future )?(visa )?sponsorship|not eligible for (visa )?sponsorship"),
    ("grad window", r"(graduating|graduation date|expected to graduate|graduate) (in|between|from|during)[^.]{0,40}(2027|2028)|class of (2027|2028)|(2027|2028) (start|new grads?|graduates)|"
                    r"degree (by|in|before|no later than) [^.]{0,30}(2027|2028)|(currently|actively) (enrolled|pursuing)[^.]{0,60}(degree|program|university)|"
                    r"rising (junior|senior)|returning to school"),  # 10-07 rejection from a 2027-grad rotational program: "Bachelor's Degree by May/June 2027"
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


_BLOCKERS_RX = [(name, re.compile(pat)) for name, pat in BLOCKERS]
_STACK_RX = {name: (re.compile(r"(?<![a-z0-9])" + s + r"(?![a-z0-9])"),
                    re.compile(REQUIRED_CUE.replace("{s}", r"(?<![a-z0-9])(?:" + s + r")(?![a-z0-9])")),
                    re.compile(s)) for name, s in CORE_STACKS.items()}
_MISSING = {"key": None, "stacks": ()}
# "5+ years", "4-7 years", "5 to 15+ years": the lower bound is the requirement
_YEARS = re.compile(r"(?<![\d.])(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*\d{1,2}\s*\+?\s*)?years?(?: of)?[^.]{0,60}experience")


def missing_stacks():
    """Core stacks the Fact Bank doesn't list: O(stacks * T) once per vocabulary, then O(1)."""
    have = vocabulary()
    if _MISSING["key"] is not have:
        _MISSING.update(key=have, stacks=tuple(name for name, (word, _, full) in _STACK_RX.items()
                                               if not any(full.fullmatch(t) or word.search(t) for t in have)))
    return _MISSING["stacks"]


def fit(jd, max_years=None):
    """List of hard blockers found in the job description (empty = clear)."""
    max_years = user_years() if max_years is None else max_years
    # Greenhouse JDs arrive HTML-escaped (&lt;li&gt;Bachelor&#39;s...): unescape first, or tags and apostrophes hide
    # the requirement from every pattern below (found from the 10-07 rotational-program rejection)
    low = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(html.unescape(jd))).split()).lower()
    out = [name for name, rx in _BLOCKERS_RX if rx.search(low)]
    for name in missing_stacks():
        if _STACK_RX[name][1].search(low):
            out.append(f"core stack: {name}")
    yrs = [int(m.group(1)) for m in _YEARS.finditer(low)]
    yrs = [y for y in yrs if y < 20]
    if yrs and min(yrs) > max_years:
        out.append(f"{min(yrs)}+ yrs")
    return out
