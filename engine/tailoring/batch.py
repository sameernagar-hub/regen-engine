"""Turn queued jobs into an apply batch: fetch each job description (Greenhouse, Ashby or Lever),
check it for hard blockers, route it to a resume lane, tailor a Fact-Bank-only resume for it,
and flag questions that need a human.

Lanes and routing rules live in profile/lanes.json (your domains). See profile.example/lanes.json.
Usage: python -m engine batch <batch-name> <job_id,job_id,...> [--force]   (ids from workspace/queue.json)
       --force   keep jobs that have JD blockers (they're still printed)
"""
import json, os, re, sys

from engine.config import WORKSPACE, in_workspace, profile_file
from engine.discovery.ats import job_description
from engine.feedback.events import record
from engine.tailoring import resume
from engine.tailoring.tailor import tailor, fit
from engine.tailoring.salary import parse_range

FLAG = re.compile(r"years|possess|experience with|clearance|citizen|export|relocat|salary|why|arbitrat", re.I)


def load_lanes():
    return json.load(open(profile_file("lanes.json"), encoding="utf-8"))


def route(cfg, title, jd):
    for lane, pattern, scope in cfg["routing"]:
        text = title if scope == "title" else title + " " + jd[:3000]
        if lane in cfg["lanes"] and re.search(pattern, text, re.I):
            return lane
    return cfg["default"]


def load_queue():
    q = {}
    for name in ("queue.json",):
        if os.path.exists(name):
            for j in json.load(open(name)):
                j.setdefault("ats", "greenhouse")  # legacy records
                q[str(j["id"])] = j
    return q


def _safe_fetch(j):
    try:
        return job_description(j)
    except Exception as e:  # one dead posting must not sink the batch
        print(f"  ! {j.get('company')} | {j.get('title')}: {e}")
        return {}, "", []


def build(name, ids, force=False):
    cfg = load_lanes()
    with in_workspace():
        q = load_queue()
        for d in ("specs", "batches", "jd"):
            os.makedirs(d, exist_ok=True)
        batch, skipped = [], []
        # JD fetches are pure network wait: fetch them all in parallel threads (one HTTP call each), then tailor in
        # order. Wall time ~ the slowest fetch instead of the sum; tailoring itself stays sequential and CPU-cheap.
        from concurrent.futures import ThreadPoolExecutor
        known = [i for i in ids if i in q]
        with ThreadPoolExecutor(max_workers=min(8, len(known) or 1)) as pool:
            fetched = dict(zip(known, pool.map(lambda i: _safe_fetch(q[i]), known)))
        for i in ids:
            if i not in q:
                print(f"  ! {i} not in queue.json (run scan / newgrad first)"); continue
            j = q[i]
            raw, jd, questions = fetched[i]
            if not jd:
                print(f"  ! {j['company']} | {j['title']}: posting is gone"); continue
            co = re.sub(r"[^A-Za-z0-9]", "", j["company"])[:20]
            short = str(i)[:12]
            json.dump(raw, open(f"jd/{j['ats']}_{co}_{short}.json", "w"), indent=1)
            blockers = fit(jd)
            label = f"{j['company']} - {j['title']}"
            if blockers:
                print(f"  x {label}: {blockers}")
                if not force:
                    skipped.append(label)
                    record("application", job=label, url=j["url"], status="SKIPPED", detail="JD: " + ", ".join(blockers), dry=False)
                    continue
            ln = route(cfg, j["title"], jd)
            spec = tailor(cfg["lanes"][ln], jd, title=j["title"], lanes=cfg["lanes"])
            cov = spec.pop("_coverage")
            spec["file"] = f"Resume_{co}_{short}.pdf"
            json.dump(spec, open(f"specs/{co}_{short}.json", "w"), indent=1)
            pdf = resume.fit(spec)
            from engine.tailoring.compose import ats_check
            cov["ats"] = ats_check(pdf, set(cov["jd_terms_you_have"]))  # what a parser reads back out of the PDF
            flagged = [qq["label"][:100] for qq in questions if qq.get("required") and FLAG.search(qq["label"])]
            print(f"{label} | {j['ats']} | lane={ln} | resume covers {len(cov['on_resume'])}/{len(cov['jd_terms_you_have'])} JD terms, ATS text {cov['ats']['score']}%"
                  + (f" | flagged: {flagged}" if flagged else ""))
            # transparency: the exact Fact Bank entries this resume used, so every claim is traceable
            record("resume", job=label, url=j["url"], lane=ln, file=spec["file"], facts=spec["roles"],
                   projects=spec.get("projects", []), skills=spec["skills"], coverage=cov)
            batch.append({"name": label, "url": j["url"], "ats": j["ats"], "resume": os.path.relpath(pdf, WORKSPACE),
                          "lane": ln, "extra": {}, "salary_range": parse_range(jd)})
        path = f"batches/{name}.json"
        json.dump(batch, open(path, "w"), indent=1)
    print(f"-> workspace/{path}: {len(batch)} jobs" + (f", {len(skipped)} skipped for JD blockers" if skipped else ""))
    return batch


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    force = "--force" in argv
    argv = [a for a in argv if a != "--force"]
    build(argv[0], argv[1].split(","), force)


if __name__ == "__main__":
    main()
