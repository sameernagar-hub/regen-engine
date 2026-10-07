"""Truthful resume tailoring.

Every bullet comes from the Fact Bank (profile/fact_bank.json). A job spec can only pick and
order fact ids, set the headline and summary, and order skills. validate() rejects any spec that
references a fact, role, project or skill that is not in the bank, so nothing can be invented.

Usage: python -m engine tailor workspace/specs/acme.json   -> workspace/out/<file>.pdf
"""
import json, re, sys, os
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

from engine.config import WORKSPACE, profile_file

FACTS = ROLES = PROJECTS = SKILLS = EDU = CONTACT = None


OVERLAPS = []


def load_bank():
    global FACTS, ROLES, PROJECTS, SKILLS, EDU, CONTACT, OVERLAPS
    if FACTS is None:
        fb = json.load(open(os.environ.get("REGEN_FACTS", profile_file("fact_bank.json")), encoding="utf-8"))
        FACTS, ROLES, PROJECTS, SKILLS, EDU, CONTACT = fb["facts"], fb["roles"], fb["projects"], fb["skills"], fb["education"], fb["contact"]
        OVERLAPS = fb.get("_overlaps", [])


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
    bad = [f"skill_text:{k}" for k, v in spec.get("skill_text", {}).items() if k not in SKILLS or strip_aliases(v) != SKILLS[k][1]]
    bad += [f"role:{r}" for r, _ in spec["roles"] if r not in ROLES]
    bad += [f"fact:{f}" for _, fids in spec["roles"] for f in fids if f not in FACTS]
    bad += [f"project:{p}" for p in spec.get("projects", []) if p not in PROJECTS]
    bad += [f"skill:{k}" for k in spec["skills"] if k not in SKILLS]
    if bad:
        raise SystemExit("spec references entries not in the Fact Bank: " + ", ".join(bad))

S = lambda n, **k: ParagraphStyle(n, fontName=k.pop("f", "Helvetica"), fontSize=k.pop("s", 9.3), leading=k.pop("l", 11.6), **k)
NAME = S("n", f="Helvetica-Bold", s=16, l=19, alignment=TA_CENTER)
CON = S("c", s=8.6, l=10.5, alignment=TA_CENTER)
HEAD = S("h", f="Helvetica-Bold", s=9.2, l=11.5, alignment=TA_CENTER, spaceAfter=2)
SEC = S("sec", f="Helvetica-Bold", s=10.2, l=12.5, spaceBefore=6)
BODY = S("b")
BUL = S("bul", leftIndent=10, bulletIndent=1, spaceAfter=1)
L = S("l", f="Helvetica-Bold", s=9.4)
R = S("r", s=9.2, alignment=2)

def row(left, right):
    t = Table([[Paragraph(left, L), Paragraph(right, R)]], colWidths=[6.0 * inch, 1.5 * inch])
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t

def section(story, title):
    story += [Paragraph(title, SEC), HRFlowable(width="100%", thickness=0.6, spaceBefore=1, spaceAfter=3)]

def build(spec):
    load_bank()
    os.makedirs(os.path.join(WORKSPACE, "out"), exist_ok=True)
    out = os.path.join(WORKSPACE, "out", spec["file"])
    st = [Paragraph(CONTACT["name"], NAME), Paragraph(CONTACT["line"], CON),
          Paragraph(spec["headline"], HEAD)]
    section(st, "SUMMARY"); st.append(Paragraph(spec["summary"], BODY))
    section(st, "EXPERIENCE")
    for rk, fids in spec["roles"]:
        c, t, loc, d = ROLES[rk]
        st.append(row(f"{c} -- {t}, {loc}", d))
        st += [Paragraph(FACTS[f], BUL, bulletText="•") for f in fids]
    if spec.get("projects"):
        section(st, "PROJECTS")
        for pk in spec["projects"]:
            n, d, bs = PROJECTS[pk]
            st.append(row(n, d)); st += [Paragraph(b, BUL, bulletText="•") for b in bs]
    section(st, "TECHNICAL SKILLS")
    st += [Paragraph(f"<b>{SKILLS[k][0]}:</b> {spec.get('skill_text', {}).get(k, SKILLS[k][1])}", BUL, bulletText="•")
           for k in spec["skills"]]
    section(st, "EDUCATION")
    st += [row(e, d) for e, d in EDU]
    SimpleDocTemplate(out, pagesize=letter, leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                      topMargin=0.42 * inch, bottomMargin=0.4 * inch,
                      title=CONTACT["name"].title() + " Resume", author=CONTACT["name"].title()).build(st)
    return out

def fit(spec):
    """Shrink leading/font a little at a time until the resume is one page."""
    from pypdf import PdfReader
    global BODY, BUL
    validate(spec)
    for lead, size in [(11.6, 9.3), (11.2, 9.2), (10.9, 9.1), (10.6, 9.0), (10.3, 8.9), (10.0, 8.8)]:
        BODY = S("b", s=size, l=lead); BUL = S("bul", s=size, l=lead, leftIndent=10, bulletIndent=1, spaceAfter=1)
        out = build(spec)
        if len(PdfReader(out).pages) == 1: return out
    raise SystemExit("still 2 pages: drop a bullet from the spec")

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    print(fit(json.load(open(argv[0]))))


if __name__ == "__main__":
    main()
