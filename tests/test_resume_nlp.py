"""The resume classifier (engine/resume_nlp.py): every kind of resume, the traps, the benchmark, and the web port."""
import importlib.util, json, os, shutil, subprocess, sys

from engine import resume_nlp as N
from resume_corpus import CORPUS, TITLES, PARITY_TITLES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BENCH = _load("tests/resume_bench.py", "resume_bench_set").BENCH


def test_every_corpus_resume_gets_its_family():
    wrong = [(want, N.analyze(text)["label"], text[:50]) for want, text in CORPUS if N.analyze(text)["label"] != want]
    assert not wrong


def test_posting_titles_land_in_the_same_taxonomy():
    assert [t for t, want in TITLES if (N.classify_title(t) or [""])[0] != want] == []


def test_employer_names_and_mentions_do_not_decide_the_label():
    # the 11-18 bug: "Cloud Software" in an employer name made an Account Executive read as software
    assert N.analyze("Registered Nurse at Software Engineering Corp, 2019-2024. Patient care, triage.")["label"] == "healthcare"
    assert N.analyze("Software Engineer at Mercy Hospital, 2019-2024. Built REST APIs and microservices in Java.")["label"] == "software"
    recruiter = next(t for w, t in CORPUS if w == "people / hr")  # hires software engineers all day
    assert N.analyze(recruiter)["label"] == "people / hr"


def test_too_little_evidence_is_unclassified_not_software():
    for text in ("", "Hello world.", "I want to be a software engineer. I like computers."):
        a = N.analyze(text)
        assert a["label"] == "unclassified" and a["labels"] == [] and a["level"] == "none"


def test_career_changer_reads_by_current_role_and_keeps_the_old_one_as_secondary():
    text = next(t for w, t in CORPUS if "Startup Labs" in t)
    a = N.analyze(text)
    assert a["labels"][0] == "software" and "education" in a["labels"] and a["hybrid"]


def test_pipeline_steps_are_reported():
    s = N.analyze(CORPUS[0][1])["steps"]
    assert s["tokens"] > s["terms"] > 0 and s["stopwords"] > 0 and s["aliases"] >= 1
    assert s["sections"][:3] == ["summary", "skills", "experience"] and s["roles"] == 3
    assert s["scores"][0]["family"] == "sales" and "account executiv" in s["scores"][0]["evidence"]


def test_tokenizer_keeps_tech_tokens_and_drops_noise():
    assert N.tokens("C++ and C# on .NET with Node.js; A/B testing; CI/CD; k8s") == \
        ["c", "plus", "plus", "c", "sharp", "dot", "net", "node", "javascript", "ab", "testing", "ci", "cd", "kubernet"]
    assert N.tokens("C-level stakeholders") == ["c", "level", "stakeholder"]


def test_held_out_benchmark_holds_and_the_site_json_is_current():
    rb = _load("scripts/resume_bench.py", "resume_bench_script")
    r = rb.evaluate()
    assert r["accuracy"] >= 0.95 and r["macro"]["f1"] >= 0.95
    assert min(r["robustness"].values()) >= 0.9
    with open(os.path.join(ROOT, "apps", "web", "lib", "resume-bench.json"), encoding="utf-8") as f:
        old = json.load(f)
    strip = lambda d: json.dumps({k: v for k, v in d.items() if k not in ("ms_per_resume", "run")}, sort_keys=True)
    assert strip(old) == strip(r), "run python scripts/resume_bench.py"


def test_web_port_gives_the_same_answers(tmp_path):
    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node not installed")
    lib = os.path.join(ROOT, "apps", "web", "lib")
    src = open(os.path.join(lib, "resume-nlp.ts"), encoding="utf-8").read()
    src = src.replace('import R from "./try-rules.json";', 'import R from "./try-rules.json" with { type: "json" };')
    (tmp_path / "resume-nlp.mts").write_text(src, encoding="utf-8")
    shutil.copy(os.path.join(lib, "try-rules.json"), tmp_path / "try-rules.json")
    texts = [t for _, t in CORPUS + BENCH]
    titles = [t for t, _ in TITLES] + PARITY_TITLES
    (tmp_path / "in.json").write_text(json.dumps({"texts": texts, "titles": titles}), encoding="utf-8")
    (tmp_path / "run.mts").write_text(
        'import { readFileSync } from "node:fs";\nimport { analyze, classifyTitle } from "./resume-nlp.mts";\n'
        'const i = JSON.parse(readFileSync(process.argv[2], "utf8"));\n'
        'console.log(JSON.stringify({ a: i.texts.map((t) => analyze(t)), t: i.titles.map((t) => classifyTitle(t)) }));\n',
        encoding="utf-8")
    p = subprocess.run([node, "--experimental-strip-types", "--no-warnings", str(tmp_path / "run.mts"), str(tmp_path / "in.json")],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    if p.returncode and "strip-types" in p.stderr:
        import pytest
        pytest.skip("node without TypeScript stripping")
    assert p.returncode == 0, p.stderr[-800:]
    out = json.loads(p.stdout)
    for text, ts in zip(texts, out["a"]):
        py = N.analyze(text)
        assert ts["labels"] == py["labels"] and abs(ts["confidence"] - py["confidence"]) <= 0.002, text[:60]
        for k in ("tokens", "terms", "sections", "roles", "sample", "phrases"):
            assert ts["steps"][k] == py["steps"][k], (k, text[:60])
    assert out["t"] == [N.classify_title(t) for t in titles]
