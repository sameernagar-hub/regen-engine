"""Truthful resume tailoring.

Every bullet comes from the Fact Bank (profile/fact_bank.json). A job spec can only pick and
order fact ids, set the headline and summary, and order skills. validate() rejects any spec that
references a fact, role, project or skill that is not in the bank, so nothing can be invented.

Usage: python -m engine tailor workspace/specs/acme.json   -> workspace/out/<file>.pdf
"""
import json, re, sys, os
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

from engine.config import WORKSPACE, profile_file

FACTS = ROLES = PROJECTS = SKILLS = EDU = CONTACT = None
VARIANTS = {}  # 11-05: fid -> one-line rewordings of that same fact, each leading with a different angle


OVERLAPS = []


def load_bank():
    global FACTS, ROLES, PROJECTS, SKILLS, EDU, CONTACT, OVERLAPS, VARIANTS, ROLE_PREFIX
    if FACTS is None:
        fb = json.load(open(os.environ.get("REGEN_FACTS", profile_file("fact_bank.json")), encoding="utf-8"))
        FACTS, ROLES, PROJECTS, SKILLS, EDU, CONTACT = fb["facts"], fb["roles"], fb["projects"], fb["skills"], fb["education"], fb["contact"]
        OVERLAPS = fb.get("_overlaps", [])
        VARIANTS = fb.get("variants", {})
        ROLE_PREFIX = fb.get("role_prefix", {})


ROLE_PREFIX = {}


def texts(fid):
    """Every wording the bank holds for one fact: index 0 is the fact itself, then its variants."""
    return [FACTS[fid]] + list(VARIANTS.get(fid, []))


def width(text, size):
    """Printed width in points of a bullet's text (bold runs measured in bold)."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    w, bold = 0.0, False
    for part in re.split(r"(</?b>)", text):
        if part in ("<b>", "</b>"):
            bold = part == "<b>"
            continue
        w += stringWidth(html_unescape(re.sub(r"<[^>]+>", "", part)), "Helvetica-Bold" if bold else "Helvetica", size)
    return w


def html_unescape(t):
    import html
    return html.unescape(t)


LINE_W = 8.5 * 72 - 2 * 0.45 * 72 - 9 - 2  # page width - margins - bullet indent - safety


def pick_text(spec, fid, size):
    """The first wording in the spec's JD-ranked order that fits on one printed line; else the narrowest one."""
    opts = texts(fid)
    order = [i for i in spec.get("fact_pick", {}).get(fid, []) if i < len(opts)] or list(range(len(opts)))
    for i in order:
        if width(opts[i], size) <= LINE_W:
            return opts[i]
    WRAPPED.append(fid)
    return min(opts, key=lambda t: width(t, size))


WRAPPED = []


# Same skill, other spellings a JD (and its ATS keyword scan) may use. A skills line may show "Canonical (Alias)" only
# for a canonical term already on that line, so the wording follows the JD without adding anything new.
ALIASES = {
    "PostgreSQL": ["Postgres"], "JavaScript": ["ECMAScript"], "Node.js": ["NodeJS"], "Kubernetes": ["K8s"],
    "Go": ["Golang"], "REST APIs": ["RESTful APIs", "RESTful"], "React": ["React.js", "ReactJS"],
    "Spring Boot 3": ["Spring Boot", "Spring"], "LLMs": ["large language models"], "CI/CD": ["continuous integration"],
    "RAG": ["retrieval-augmented generation", "retrieval augmented generation"], "Kafka": ["Apache Kafka"],
    "microservices": ["microservice architecture", "service-oriented architecture"],
    "AWS": ["Amazon Web Services"], "embeddings and vector search": ["vector databases", "semantic search"],
}


def _term(t):
    return r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])"


def jd_spelling(line, jd):
    """Skills line with the JD's spelling added next to each canonical term it names differently."""
    low = " ".join(re.sub(r"<[^>]+>", " ", jd or "").split()).lower()
    for canon, alts in ALIASES.items():
        if not re.search(_term(canon), line) or re.search(_term(canon.lower()), low):
            continue
        hit = next((a for a in alts if not re.search(_term(a.lower()), canon.lower()) and re.search(_term(a.lower()), low)), None)
        if hit:
            line = re.sub(_term(canon), f"{canon} ({hit})", line, count=1)
    return line


def strip_aliases(line):
    for canon, alts in ALIASES.items():
        for a in alts:
            line = line.replace(f"{canon} ({a})", canon)
    return line


def validate(spec):
    """Truthfulness gate: a spec may only reference entries that exist in the Fact Bank."""
    load_bank()
    from engine.tailoring.compose import same_items  # v0.9: a line may be reordered for the JD, never changed
    bad = [f"skill_text:{k}" for k, v in spec.get("skill_text", {}).items() if k not in SKILLS or not same_items(strip_aliases(v), SKILLS[k][1])]
    bad += [f"role:{r}" for r, _ in spec["roles"] if r not in ROLES]
    bad += [f"fact:{f}" for _, fids in spec["roles"] for f in fids if f not in FACTS]
    bad += [f"fact_pick:{f}" for f, ix in spec.get("fact_pick", {}).items() if f not in FACTS or any(i >= len(texts(f)) for i in ix)]
    bad += [f"project:{p}" for p in spec.get("projects", []) if p not in PROJECTS]
    bad += [f"skill:{k}" for k in spec["skills"] if k not in SKILLS]
    if bad:
        raise SystemExit("spec references entries not in the Fact Bank: " + ", ".join(bad))

S = lambda n, **k: ParagraphStyle(n, fontName=k.pop("f", "Helvetica"), fontSize=k.pop("s", 8.7), leading=k.pop("l", 10.3), **k)
# 11-05 (user): smaller type, every line used, text justified so both edges align
NAME = S("n", f="Helvetica-Bold", s=14.5, l=16.5, alignment=TA_CENTER)
CON = S("c", s=8.2, l=9.8, alignment=TA_CENTER)
HEAD = S("h", f="Helvetica-Bold", s=8.7, l=10.4, alignment=TA_CENTER, spaceAfter=1)
SEC = S("sec", f="Helvetica-Bold", s=9.4, l=11, spaceBefore=3.5)
BODY = S("b", alignment=TA_JUSTIFY)
BUL = S("bul", leftIndent=9, bulletIndent=1, spaceAfter=0.4, alignment=TA_JUSTIFY)
L = S("l", f="Helvetica-Bold", s=8.9)
R = S("r", s=8.7, alignment=2)
SIZES = [(11.4, 9.6), (11.0, 9.3), (10.7, 9.1), (10.4, 8.9), (10.2, 8.8), (10.0, 8.7), (9.8, 8.6), (9.6, 8.5), (9.4, 8.4), (9.2, 8.3), (9.0, 8.2), (8.8, 8.1)]

def row(left, right):
    t = Table([[Paragraph(left, L), Paragraph(right, R)]], colWidths=[6.0 * inch, 1.6 * inch])
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5)]))
    return t

def section(story, title):
    story += [Paragraph(title, SEC), HRFlowable(width="100%", thickness=0.5, spaceBefore=0.5, spaceAfter=1.5)]

def build(spec):
    load_bank()
    WRAPPED.clear()
    os.makedirs(os.path.join(WORKSPACE, "out"), exist_ok=True)
    out = os.path.join(WORKSPACE, "out", spec["file"])
    st = [Paragraph(CONTACT["name"], NAME), Paragraph(CONTACT["line"], CON),
          Paragraph(spec["headline"], HEAD)]
    section(st, "SUMMARY"); st.append(Paragraph(spec["summary"], BODY))
    section(st, "EXPERIENCE")
    for rk, fids in spec["roles"]:
        c, t, loc, d = ROLES[rk]
        st.append(row(f"{c} -- {t}, {loc}", d))
        st += [Paragraph(pick_text(spec, f, BUL.fontSize), BUL, bulletText="•") for f in fids]
    if spec.get("projects"):
        section(st, spec.get("projects_title", "PROJECTS"))
        for pk in spec["projects"]:
            n, d, bs = PROJECTS[pk]
            st.append(row(n, d or "")); st += [Paragraph(b, BUL, bulletText="•") for b in bs]
    section(st, "TECHNICAL SKILLS")
    st += [Paragraph(f"<b>{SKILLS[k][0]}:</b> {spec.get('skill_text', {}).get(k, SKILLS[k][1])}", BUL, bulletText="•")
           for k in spec["skills"]]
    if spec.get("jd_keywords"):  # 11-05: the posting's remaining keywords (keywords.py; user-approved, logged per job)
        st.append(Paragraph("<b>Role Keywords:</b> " + ", ".join(spec["jd_keywords"]), BUL, bulletText="•"))
    section(st, "EDUCATION")
    st += [row(e, d) for e, d in EDU]
    SimpleDocTemplate(out, pagesize=letter, leftMargin=0.45 * inch, rightMargin=0.45 * inch,
                      topMargin=0.35 * inch, bottomMargin=0.3 * inch,
                      title=CONTACT["name"].title() + " Resume", author=CONTACT["name"].title()).build(st)
    return out

def _pages(spec, lead, size):
    from pypdf import PdfReader
    global BODY, BUL
    BODY = S("b", s=size, l=lead, alignment=TA_JUSTIFY)
    BUL = S("bul", s=size, l=lead, leftIndent=9, bulletIndent=1, spaceAfter=0.4, alignment=TA_JUSTIFY)
    return len(PdfReader(build(spec)).pages)


def _grow(spec):
    """Next spec with one more Fact Bank entry from the ranked reserve (spec["_more"]): roles round-robin, then a
    project. None when the reserve is empty. Only bank ids are added, so validate() still holds."""
    more = spec.get("_more") or {}
    roles = [[rk, list(f)] for rk, f in spec["roles"]]
    used = {f for _, fids in roles for f in fids}
    best = None
    for i, (rk, fids) in enumerate(roles):
        nxt = next((f for f in more.get(rk, []) if f not in used), None)
        if nxt and (best is None or len(fids) < len(roles[best[0]][1])):
            best = (i, nxt)
    if best:
        roles[best[0]][1].append(best[1])
        return dict(spec, roles=roles)
    projs = list(spec.get("projects") or [])
    nxt = next((p for p in more.get("_projects", []) if p not in projs), None)
    return dict(spec, projects=projs + [nxt]) if nxt else None


def fit(spec):
    """One page, as full as possible (11-05): grow the spec with ranked reserve bullets while it fits at the
    largest readable size, then shrink type a step at a time if it overflows."""
    validate(spec)
    lead, size = SIZES[0]
    cur = spec
    target = SIZES[-2]  # fill to this size; the very smallest step stays as overflow room
    if _pages(cur, *target) == 1:
        for _ in range(40):  # fill: keep adding while one page holds at the target size
            nxt = _grow(cur)
            if nxt is None or _pages(nxt, *target) > 1:
                break
            cur = nxt
    for lead, size in SIZES:  # then the largest type that still fits
        if _pages(cur, lead, size) == 1:
            spec.update(roles=cur["roles"], projects=cur.get("projects", []))
            out = build(cur)
            spec["_qa"] = qa(out, cur, size)
            return out
    if len(cur.get("projects") or []) > 1:
        return fit(dict(cur, projects=cur["projects"][:-1], _more={}))
    raise SystemExit("still 2 pages: drop a bullet from the spec")


def fill_ratio(pdf):
    """How far down the page the text reaches (1.0 = the bottom margin)."""
    from pypdf import PdfReader
    page = PdfReader(pdf).pages[0]
    ys = []
    page.extract_text(visitor_text=lambda t, cm, tm, fd, fs: ys.append(tm[5] * cm[3] + cm[5]) if t.strip() else None)
    h = float(page.mediabox.height)
    top, bottom = h - 0.35 * 72, 0.3 * 72
    return round((top - min(ys)) / (top - bottom), 3) if ys else 0.0


def qa(pdf, spec, size):
    """Self-test of one built resume (11-05): one page, bullets on one line, page filled, no repeated fact."""
    from pypdf import PdfReader
    fids = [f for _, fs in spec["roles"] for f in fs]
    return {"pages": len(PdfReader(pdf).pages), "size": size, "bullets": len(fids), "wrapped": list(WRAPPED),
            "fill": fill_ratio(pdf), "duplicates": len(fids) - len(set(fids)),
            "picks": {f: texts(f).index(pick_text(spec, f, size)) for f in fids}}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    print(fit(json.load(open(argv[0]))))


if __name__ == "__main__":
    main()
