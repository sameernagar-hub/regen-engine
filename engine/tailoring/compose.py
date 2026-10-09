"""JD-first composition (v0.9): the parts of a resume that should read as if written for this one posting.

The user's own hand-tailored resumes (Zoox Embedded, Google SRE, 2026-10-08) set the bar: the headline names the role
and the 3-4 things the posting cares about most, the summary leads with the sentences that answer the posting, skills
lines put the posting's terms first, and the projects section is named for the work ("Embedded & Systems Work").
Nothing here can add a claim: every sentence, skill and fact still comes from the Fact Bank or a lane the user wrote,
and resume.validate() checks the result.

  headline(title, jd, lane_headline)  role from the posting title + top JD terms the candidate has, by JD frequency
  summary(jd, lane, lanes)            lane opener + the best-matching sentences from every user-written lane summary
  order_skill_line(line, want)        same items, JD terms first (validate compares the item set, not the order)
  ats_check(pdf, want)                text a parser extracts from the PDF, and which JD terms survive extraction

Complexity: S = summary sentences (~40), T = JD terms the candidate has (~30), n = JD length.
  term frequency O(T*n) once per JD; summary ranking O(S*T); headline O(T log T); skill lines O(items*T).
"""
import html
import re

LEVEL = re.compile(r"\b(senior|sr\.?|staff|principal|lead|junior|jr\.?|intern(ship)?|new grad(uate)?|early career|entry[- ]level|"
                   r"i{1,3}|iv|[1-4])\b|\(.*?\)|,.*$| - .*$| \| .*$|\s+[–—-]\s+.*$", re.I)


def plain(jd):
    return " ".join(re.sub(r"<[^>]+>", " ", html.unescape(html.unescape(jd or ""))).split()).lower()


def _count(term, low):
    return len(re.findall(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", low))


def ranked_terms(jd, want):
    """JD terms the candidate has, most-mentioned first (ties: longer, more specific term first)."""
    low = plain(jd)
    return sorted(want, key=lambda t: (-_count(t, low), -len(t), t))


def display(term, skills):
    """The Fact Bank's own spelling of a term ("kubernetes" -> "Kubernetes")."""
    for _, line in skills.values():
        m = re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", line, re.I)
        if m:
            return m.group(0)
    return term


def role_name(title):
    """'Senior Software Engineer II, Payments (Remote)' -> 'Software Engineer'. Level words go: the resume claims none."""
    t = LEVEL.sub(" ", title or "")
    t = " ".join(w for w in t.split() if w)
    return t.strip(" ,-|/") or "Software Engineer"


GENERIC = {"platform", "process", "engineering", "hardware", "software", "systems", "data", "cloud", "testing", "design",
           "development", "production", "linux", "git", "api", "apis", "security", "openai", "claude", "gemini", "documentation",
           "mentoring", "code review", "debugging", "automation", "unit testing", "monitoring", "sql"}


def skill_items(skills):
    """Every comma item of every skills line, parentheses removed: the headline may only name these."""
    out = []
    for _, line in skills.values():
        for it in re.split(r",(?![^()]*\))|;", line):
            it = re.sub(r"\s*\(.*?\)|\s*/.*$", "", it).strip()
            if 2 <= len(it) <= 26 and it.lower() not in GENERIC and not re.search(r"\d+x|certified", it, re.I):
                out.append(it)
    return list(dict.fromkeys(out))


def headline(title, jd, want, skills, lane_headline, n=3):
    """Role + the n skill items the posting mentions most (a skill item, never a loose word like 'platform')."""
    low = plain(jd)
    scored = [(sum(_count(t, low) for t in want if t not in GENERIC and re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", it.lower())), i, it)
              for i, it in enumerate(skill_items(skills))]
    terms, seen = [], set()
    for sc, _, it in sorted(scored, key=lambda x: (-x[0], x[1])):
        k = it.lower()
        if sc == 0 or len(terms) == n:
            break
        if any(k in s or s in k for s in seen):
            continue
        seen.add(k)
        terms.append(it)
    if len(terms) < 2:
        return lane_headline
    return " | ".join([role_name(title)] + terms)


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text or "") if len(s.strip()) > 20]


def summary(jd, lane, lanes, hits, max_sentences=4):
    """Opener from the routed lane, then the user-written sentences (any lane) that answer the most JD terms."""
    own = _sentences(lane.get("summary", ""))
    if not own:
        return lane.get("summary", "")
    first_person = bool(re.search(r"\b(I|my|me)\b", lane.get("summary", "")))
    pool = [x for x in dict.fromkeys(own[1:] + [s for l in lanes.values() for s in _sentences(l.get("summary", ""))]) if x != own[0]]
    pos = {s: i for i, s in enumerate(pool)}
    best = sorted(pool, key=lambda s: (-len(hits(s)), pos[s]))
    out, covered = [own[0]], set(hits(own[0]))
    for s in best:
        if len(out) == max_sentences:
            break
        new = hits(s) - covered
        if not new and s not in own:  # a borrowed sentence must bring a JD term the summary doesn't have yet
            continue
        # "I" voice and "he/his" voice never mix in one paragraph
        if s not in own and (bool(re.search(r"\b(I|my|me)\b", s)) != first_person
                             or first_person and re.search(r"\b(his|her|he|she)\b", s)):
            continue
        out.append(s)
        covered |= hits(s)
    order = {s: i for i, s in enumerate(own)}
    head, rest = out[0], out[1:]
    rest.sort(key=lambda s: order.get(s, 99))  # the lane's own sentences keep their order, borrowed ones follow
    return " ".join([head] + rest)


def order_skill_line(line, want):
    """Same comma items, the ones the JD names first. Parenthesised groups stay whole ("AWS (EKS, Lambda)")."""
    if ";" in line:  # "5x Certified; Apex, LWC": a credential line reads wrong reordered
        return line
    items, depth, cur = [], 0, ""
    for ch in line:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            items.append(cur.strip()); cur = ""
        else:
            cur += ch
    items.append(cur.strip())
    low = lambda s: s.lower()
    score = lambda it: -sum(1 for t in want if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low(it)))
    pos = {it: i for i, it in enumerate(items)}
    return ", ".join(sorted(items, key=lambda it: (score(it), pos[it])))


def same_items(a, b):
    split = lambda s: sorted(x.strip() for x in re.split(r",(?![^()]*\))", s))
    return split(a) == split(b)


def ats_check(pdf, want):
    """What an ATS parser sees: the PDF's extracted text, and which JD terms are readable in it."""
    from pypdf import PdfReader
    text = " ".join((p.extract_text() or "") for p in PdfReader(pdf).pages)
    low = " ".join(text.split()).lower()
    found = sorted(t for t in want if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low))
    return {"chars": len(text), "jd_terms_found_in_pdf_text": found,
            "score": round(100 * len(found) / len(want)) if want else 100}
