"""One-off tailored resume (11-24, user: "a skill for resume so you do not have to draft it again and again").
The same path the batch builder uses for every application, for a job description you paste or save to a file:
route to a lane -> tailor (Fact Bank only, validate() gates it) -> one-page PDF -> QA gate (1 page, no duplicates)
-> ATS read-back score. Nothing is invented; a JD term the Fact Bank lacks is reported, never added.

    python -m engine resume <jd.txt|-> --title "Software Engineer" [--company Acme] [--out workspace/out]
    -> prints JSON: {pdf, lane, covers, missing_terms, ats_score, qa, blockers}
"""
import json, os, re, sys

from engine.config import WORKSPACE, in_workspace


def build(jd, title, company="Resume", out_dir=None):
    from engine.tailoring import compose, resume, selftest
    from engine.tailoring.batch import load_lanes, route
    from engine.tailoring.tailor import tailor, fit
    cfg = load_lanes()
    blockers = fit(jd)
    lane = route(cfg, title, jd)
    spec = tailor(cfg["lanes"][lane], jd, title=title, lanes=cfg["lanes"], url="")
    cov = spec.pop("_coverage")
    co = re.sub(r"[^A-Za-z0-9]", "", company)[:24] or "Resume"
    role = re.sub(r"[^A-Za-z0-9]", "", title)[:24]
    spec["file"] = f"Resume_{co}_{role}.pdf"
    with in_workspace():
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        pdf = resume.fit(spec)
        if out_dir:
            dst = os.path.join(out_dir, spec["file"])
            if os.path.abspath(pdf) != os.path.abspath(dst):
                import shutil
                shutil.copyfile(pdf, dst)
                pdf = dst
        ats = compose.ats_check(pdf, set(cov["jd_terms_you_have"]))
    qa = spec.get("_qa") or {}
    return {"pdf": os.path.abspath(os.path.join(WORKSPACE, pdf)) if not os.path.isabs(pdf) else pdf, "lane": lane,
            "covers": f"{len(cov['on_resume'])}/{len(cov['jd_terms_you_have'])}",
            "missing_terms": sorted(set(cov.get("jd_terms_missing") or []))[:30],
            "ats_score": ats.get("score"), "qa": qa, "qa_ok": not qa or (qa.get("pages") == 1 and not qa.get("duplicates")),
            "qa_note": selftest.why(qa, ats.get("score")) if qa else "", "blockers": blockers}


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    src, opts, it = argv[0], {"title": "", "company": "Resume", "out": None}, iter(argv[1:])
    for a in it:
        if a.startswith("--") and a[2:] in opts:
            opts[a[2:]] = next(it, "")
        else:
            raise SystemExit(__doc__)
    jd = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    if not opts["title"]:
        raise SystemExit("--title is required (it picks the lane and the headline)")
    print(json.dumps(build(jd, opts["title"], opts["company"], opts["out"]), indent=1, default=str))
