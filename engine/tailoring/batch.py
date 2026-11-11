"""Turn queued jobs into an apply batch: fetch each job description (Greenhouse, Ashby or Lever),
check it for hard blockers, route it to a resume lane, tailor a Fact-Bank-only resume for it,
and flag questions that need a human.

Lanes and routing rules live in profile/lanes.json (your domains). See profile.example/lanes.json.
Usage: python -m engine batch <batch-name> <job_id,job_id,...> [--force]   (ids from workspace/queue.json)
       --force   keep jobs that have JD blockers (they're still printed)
"""
import json
import os, re, sys, time

from engine.config import WORKSPACE, in_workspace, profile_file
from engine.discovery.ats import job_description
from engine.feedback.events import record
from engine.tailoring import compose, keywords, resume
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


FETCH_ERROR = "fetch error"


def _safe_fetch(j):
    try:
        return job_description(j)
    except Exception as e:  # one dead posting must not sink the batch
        print(f"  ! {j.get('company')} | {j.get('title')}: {e}")
        return FETCH_ERROR, "", []  # a network error: worth another pass (a 404 / missing job means removed)


def _terms_in(text):
    from engine.tailoring.tailor import _hits, vocabulary
    return _hits(text, vocabulary())


def _match(cov):
    from engine.discovery.priority import jd_match
    return jd_match(cov)


def _hourly_checks():
    """11-05 feedback loop: recount wording outcomes, then self-test the resume pipeline on recent JDs (once an hour).
    Returns a reason string when the self-test fails on most samples (the batch then stops), else None."""
    from engine.tailoring import learn, selftest
    stamp = os.path.join(WORKSPACE, "selftest.json")
    try:
        if os.path.exists(stamp) and time.time() - os.path.getmtime(stamp) < 3600:
            rep = json.load(open(stamp))
        else:
            learn.refresh()
            rep = selftest.run(quiet=True)
            print(f"selftest: {rep['passed']}/{rep['of']} resumes pass the QA gate; wording stats refreshed", flush=True)
    except Exception as e:  # the checks never stop the engine by crashing
        print(f"selftest skipped: {str(e)[:100]}", flush=True)
        return None
    if rep["of"] >= 4 and rep["passed"] < rep["of"] / 2:
        return f"resume self-test failing ({rep['passed']}/{rep['of']}): " + "; ".join({r["why"] for r in rep["rows"] if not r["ok"]})[:200]
    return None


def build(name, ids, force=False):
    cfg = load_lanes()
    halt = _hourly_checks()
    if halt:
        print("  x batch held: " + halt, flush=True)
        return None
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
                # the ATS answered without the posting (404, not on the board): closed, so it leaves the queue
                # (10-17: three such jobs took a selection slot and a fetch every pass). A fetch error stays.
                if raw != FETCH_ERROR:
                    print(f"  ! {j['company']} | {j['title']}: posting is gone")
                    record("application", job=f"{j['company']} - {j['title']}", url=j["url"], status="SKIPPED",
                           detail="JD: posting is gone", dry=False)
                continue
            co = re.sub(r"[^A-Za-z0-9]", "", j["company"])[:20]
            short = str(i)[:12]
            json.dump(raw, open(f"jd/{j['ats']}_{co}_{short}.json", "w"), indent=1)
            blockers = fit(jd)  # reads the whole description: sponsorship, clearance, years, grad window, stack, defense
            # some employers state the citizenship requirement only in a required form question (10-11: "this role
            # requires US citizenship" on a Greenhouse form, JD silent): read those labels with the same rule
            # 10-18: the title can say it too ("Full Stack Developer [U.S. Citizenship Required, Public Trust ...]")
            req = " ".join(qq["label"] for qq in questions if qq.get("required")) + " " + j["title"]
            for b in ("citizenship", "clearance"):
                if b not in blockers and b in fit(req, max_years=99):
                    blockers.append(b)
            # every stage re-checks: the title/company filter again (sources can change titles) and the trust gate
            from engine.discovery.filters import keep, load_domain
            from engine.discovery.trust import verdict
            why = keep(load_domain(), j["title"], j.get("location") or "", j["company"])
            if why:
                blockers.append(why)
            trusted, distrust = verdict(j["url"], jd, j["company"])
            blockers += distrust
            label = f"{j['company']} - {j['title']}"
            if blockers:
                print(f"  x {label}: {blockers}")
                if not force or not trusted:  # --force never overrides the trust gate
                    skipped.append(label)
                    record("application", job=label, url=j["url"], status="SKIPPED", detail="JD: " + ", ".join(blockers), dry=False)
                    continue
            ln = route(cfg, j["title"], jd)
            spec = tailor(cfg["lanes"][ln], jd, title=j["title"], lanes=cfg["lanes"], url=j["url"])
            cov = spec.pop("_coverage")
            from engine import targeting  # NEXT_STEPS §3 skip_unsure: no blocker, but too little overlap to call it a fit
            why_unsure = targeting.unsure(jd, cov["jd_terms_you_have"])
            if why_unsure and not force:
                print(f"  x {label}: {why_unsure}"); skipped.append(label)
                record("application", job=label, url=j["url"], status="SKIPPED", detail="JD: " + why_unsure, dry=False)
                continue
            note = compose.cover_note(j["title"], j["company"], jd, spec, cov["jd_terms_you_have"], resume.FACTS,
                                      resume.ROLES, resume.SKILLS, lambda t: set(cov["jd_terms_you_have"]) & _terms_in(t))
            spec["file"] = f"Resume_{co}_{short}.pdf"
            json.dump(spec, open(f"specs/{co}_{short}.json", "w"), indent=1)
            try:
                pdf = resume.fit(spec)
            except SystemExit as e:  # one resume that won't fit never stops the whole batch
                print(f"  x {label}: resume: {e}"); skipped.append(label); continue
            from engine.tailoring.compose import ats_check
            from engine.tailoring import selftest
            cov["ats"] = ats_check(pdf, set(cov["jd_terms_you_have"]))  # what a parser reads back out of the PDF
            qa = spec.get("_qa") or {}
            if qa and (qa["pages"] != 1 or qa["duplicates"]):  # 11-05 QA gate: never send a broken resume
                print(f"  x {label}: resume QA: {selftest.why(qa, cov['ats']['score'])}"); skipped.append(label); continue
            flagged = [qq["label"][:100] for qq in questions if qq.get("required") and FLAG.search(qq["label"])]
            print(f"{label} | {j['ats']} | lane={ln} | resume covers {len(cov['on_resume'])}/{len(cov['jd_terms_you_have'])} JD terms, ATS text {cov['ats']['score']}%"
                  + (f" | flagged: {flagged}" if flagged else ""))
            # transparency: the exact Fact Bank entries this resume used, so every claim is traceable
            record("resume", job=label, url=j["url"], lane=ln, file=spec["file"], facts=spec["roles"],
                   projects=spec.get("projects", []), skills=spec["skills"], coverage=cov, note=note,
                   qa=spec.get("_qa"), jd_keywords=spec.get("jd_keywords", []),
                   # 11-09 funnel (NEXT_STEPS §2): ATS + posting time, so outcomes can be split by them later
                   ats=j.get("ats"), posted=j.get("posted"), keywords_on=keywords.enabled(j["url"]),
                   ab_arm=keywords.arm(j["url"]) if keywords.ab_active() else None)  # §3 A/B: the arm, logged
            batch.append({"name": label, "url": j["url"], "ats": j["ats"], "resume": os.path.relpath(pdf, WORKSPACE),
                          "lane": ln, "extra": {}, "salary_range": parse_range(jd), "jd_match": _match(cov), "note": note})
        # after reading every description: highest JD match first (stable, so ties keep queue priority)
        from engine.discovery.priority import jd_match
        batch.sort(key=lambda b: -b.get("jd_match", 0))
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
