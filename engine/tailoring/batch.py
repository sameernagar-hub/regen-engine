"""Turn queued jobs into an apply batch: fetch each job description, route it to a resume lane,
build a Fact-Bank-only resume for it, and flag questions that need a human.

Lanes and routing rules live in profile/lanes.json (your domains). See profile.example/lanes.json.
Usage: python -m engine batch <batch-name> <job_id,job_id,...>   (ids from workspace/queue.json)
"""
import html, json, os, re, sys, urllib.request

from engine.config import WORKSPACE, in_workspace, profile_file
from engine.tailoring import resume

FLAG = re.compile(r"years|possess|experience with|clearance|citizen|export|relocat|salary|why|arbitrat", re.I)


def load_lanes():
    return json.load(open(profile_file("lanes.json"), encoding="utf-8"))


def route(cfg, title, jd):
    for lane, pattern, scope in cfg["routing"]:
        text = title if scope == "title" else title + " " + jd[:3000]
        if re.search(pattern, text, re.I):
            return lane
    return cfg["default"]


def fetch_job(token, job_id):
    d = json.load(urllib.request.urlopen(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}?questions=true", timeout=20))
    jd = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(d.get("content", ""))))
    return d, jd


def build(name, ids):
    cfg = load_lanes()
    with in_workspace():
        q = {str(j["id"]): j for j in json.load(open("queue.json"))}
        os.makedirs("specs", exist_ok=True); os.makedirs("batches", exist_ok=True); os.makedirs("jd", exist_ok=True)
        batch = []
        for i in ids:
            j = q[i]; tok = j["token"]
            d, jd = fetch_job(tok, i)
            json.dump(d, open(f"jd/{tok}_{i}.json", "w"), indent=1)
            ln = route(cfg, j["title"], jd)
            spec = dict(cfg["lanes"][ln]); co = re.sub(r"[^A-Za-z0-9]", "", j["company"])[:20]
            spec["file"] = f"Resume_{co}_{i}.pdf"
            json.dump(spec, open(f"specs/{co}_{i}.json", "w"), indent=1)
            pdf = resume.fit(spec)
            flagged = [qq["label"][:100] for qq in d.get("questions", []) if qq.get("required") and FLAG.search(qq["label"])]
            print(f"{j['company']} | {j['title']} | lane={ln} | flagged: {flagged}")
            batch.append({"name": f"{j['company']} - {j['title']}", "url": f"https://job-boards.greenhouse.io/{tok}/jobs/{i}",
                          "resume": os.path.relpath(pdf, WORKSPACE), "extra": {}})
        path = f"batches/{name}.json"
        json.dump(batch, open(path, "w"), indent=1)
    print("->", os.path.join("workspace", path))
    return batch


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    build(argv[0], argv[1].split(","))


if __name__ == "__main__":
    main()
