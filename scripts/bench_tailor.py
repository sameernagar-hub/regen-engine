"""Equivalence + speed check for engine/tailoring/tailor.py against an older copy of the module.

    git show <rev>:engine/tailoring/tailor.py > /tmp/tailor_old.py
    python scripts/bench_tailor.py /tmp/tailor_old.py

Runs fit() and tailor() from both versions on every saved job description (workspace/jd/*.json), asserts the
outputs are identical, and prints ms per JD for each. Evidence for the v0.8 complexity work (see CHANGELOG).
"""
import glob, importlib.util, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.config import WORKSPACE
from engine.tailoring import tailor as NEW
from engine.tailoring.batch import load_lanes, route


def load_old(path):
    spec = importlib.util.spec_from_file_location("tailor_old", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def jds():
    out = []
    for f in sorted(glob.glob(os.path.join(WORKSPACE, "jd", "*.json"))):
        raw = json.load(open(f, encoding="utf-8"))
        out.append(raw.get("content") or raw.get("descriptionHtml") or raw.get("description") or json.dumps(raw))
    return out


def bench(mod, texts, cfg, reps=3):
    best = [float("inf"), float("inf")]
    for _ in range(reps):
        t = time.perf_counter()
        for jd in texts:
            mod.fit(jd)
        t1 = time.perf_counter()
        for jd in texts:
            mod.tailor(cfg["lanes"][route(cfg, "Software Engineer", jd)], jd)
        t2 = time.perf_counter()
        best = [min(best[0], t1 - t), min(best[1], t2 - t1)]
    return [x / len(texts) * 1e3 for x in best]


def main():
    old = load_old(sys.argv[1])
    cfg, texts = load_lanes(), jds()
    diff = 0
    for jd in texts:
        lane = cfg["lanes"][route(cfg, "Software Engineer", jd)]
        if old.fit(jd) != NEW.fit(jd) or old.tailor(lane, jd) != NEW.tailor(lane, jd):
            diff += 1
    o, n = bench(old, texts, cfg), bench(NEW, texts, cfg)
    print(f"{len(texts)} real JDs; outputs differ on {diff}")
    print(f"fit     old {o[0]:7.2f} ms/JD   new {n[0]:7.2f} ms/JD   x{o[0] / n[0]:.1f}")
    print(f"tailor  old {o[1]:7.2f} ms/JD   new {n[1]:7.2f} ms/JD   x{o[1] / n[1]:.1f}")
    sys.exit(1 if diff else 0)


if __name__ == "__main__":
    main()
