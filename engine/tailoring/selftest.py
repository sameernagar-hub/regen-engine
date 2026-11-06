"""Pipeline self-test (11-05, user: "test the pipeline itself before going to the engine").

Runs tailor + fit on the most recent saved job descriptions (workspace/jd/) without queueing anything, and checks
every resume against the QA gate. batch.build() runs it once per hour before tailoring real jobs; if the gate fails
on most samples, the batch stops and says why instead of sending weak resumes.

  python -m engine.tailoring.selftest [n]
"""
import glob
import json
import os
import sys
import time

from engine.config import WORKSPACE

GATE = {"pages": 1, "min_fill": 0.9, "max_wrapped": 2, "min_ats": 90}


def passes(qa, ats):
    return (qa["pages"] == GATE["pages"] and qa["fill"] >= GATE["min_fill"] and len(qa["wrapped"]) <= GATE["max_wrapped"]
            and qa["duplicates"] == 0 and ats >= GATE["min_ats"])


def why(qa, ats):
    out = []
    if qa["pages"] != 1: out.append(f"{qa['pages']} pages")
    if qa["fill"] < GATE["min_fill"]: out.append(f"fill {qa['fill']}")
    if len(qa["wrapped"]) > GATE["max_wrapped"]: out.append(f"{len(qa['wrapped'])} wrapped bullets")
    if qa["duplicates"]: out.append("repeated fact")
    if ats < GATE["min_ats"]: out.append(f"ATS {ats}%")
    return ", ".join(out)


def run(n=8, quiet=False):
    from engine.tailoring import batch, compose, resume
    from engine.tailoring.tailor import tailor, _hits, vocabulary
    cfg = batch.load_lanes()
    files = sorted(glob.glob(os.path.join(WORKSPACE, "jd", "*")), key=os.path.getmtime, reverse=True)[:n]
    rows = []
    for f in files:
        jd = open(f, encoding="utf-8", errors="ignore").read()
        title = os.path.basename(f).rsplit(".", 1)[0].replace("_", " ")
        try:
            spec = tailor(cfg["lanes"][batch.route(cfg, title, jd)], jd, title=title, lanes=cfg["lanes"])
            spec.pop("_coverage", None)
            spec["file"] = "_selftest.pdf"
            pdf = resume.fit(spec)
            ats = compose.ats_check(pdf, _hits(jd, vocabulary()))["score"]
            q = spec["_qa"]
            rows.append({"jd": os.path.basename(f), "ok": passes(q, ats), "why": why(q, ats), "fill": q["fill"],
                         "bullets": q["bullets"], "wrapped": len(q["wrapped"]), "ats": ats,
                         "keywords": len(spec.get("jd_keywords", []))})
        except (SystemExit, Exception) as e:
            rows.append({"jd": os.path.basename(f), "ok": False, "why": f"error: {str(e)[:80]}"})
    try:
        os.remove(os.path.join(WORKSPACE, "out", "_selftest.pdf"))
    except OSError:
        pass
    ok = sum(r["ok"] for r in rows)
    report = {"at": time.strftime("%Y-%m-%d %H:%M"), "passed": ok, "of": len(rows), "gate": GATE, "rows": rows}
    json.dump(report, open(os.path.join(WORKSPACE, "selftest.json"), "w"), indent=1)
    if not quiet:
        for r in rows:
            print(("PASS " if r["ok"] else "FAIL ") + r["jd"][:50], {k: r.get(k) for k in ("fill", "bullets", "wrapped", "ats", "keywords")}, r["why"])
        print(f"selftest: {ok}/{len(rows)} pass")
    return report


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
