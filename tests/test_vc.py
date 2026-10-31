"""Venture-portal drivers (engine/discovery/vc.py) and the per-job cover note (compose.cover_note). No network."""
from engine.discovery import vc
from engine.tailoring import compose


def test_ats_of_reads_direct_postings_only():
    assert vc.ats_of("https://boards.greenhouse.io/andurilindustries/jobs/5268869007?gh_jid=5268869007") == ("greenhouse", "andurilindustries")
    assert vc.ats_of("https://jobs.ashbyhq.com/Initech/abc-123") == ("ashby", "Initech")
    assert vc.ats_of("https://www.zipline.com/open-roles/8040723003?gh_jid=8040723003") is None
    assert vc.ats_of("https://www.ycombinator.com/companies/x/jobs/abc") is None


def test_gate_dedupes_and_drops_blank_leads(monkeypatch):
    monkeypatch.setattr(vc, "load_domain", lambda: None)
    monkeypatch.setattr(vc, "keep", lambda dom, t, loc, co: "title" if "Sales" in t else None)
    leads = [vc._lead("Acme", "Software Engineer", "SF", "u1"), vc._lead("acme", "software engineer", "NY", "u2"),
             vc._lead("Acme", "Sales Manager", "SF", "u3"), vc._lead("", "Software Engineer", "SF", "u4")]
    out, dropped = vc.gate(leads)
    assert [l["lead_url"] for l in out] == ["u1"] and dropped == {"title": 1}


def test_crawl_careers_finds_embedded_board(monkeypatch):
    pages = {"https://acme.dev/careers": '<script src="https://boards.greenhouse.io/embed/job_board/js?for=acmeco"></script>'}
    def fake(url, *a, **k):
        if url in pages:
            return pages[url]
        raise OSError("404")
    monkeypatch.setattr(vc, "_open", fake)
    assert vc.crawl_careers({"lead_url": "https://www.ycombinator.com/companies/acme/jobs/1", "domain": "https://acme.dev"}) == ("greenhouse", "acmeco")
    assert vc.crawl_careers({"lead_url": "https://www.ycombinator.com/x", "domain": None}) is None


def test_cover_note_uses_only_resume_facts_and_jd_terms():
    facts = {"acme_1": "Built Kafka pipelines in Python.", "acme_2": "Cut p95 latency 40% with Redis caching.",
             "acme_3": "Ran the hiring loop."}
    roles = {"acme": ["Acme Corp", "Software Engineer", "SF", "2022 - 2024"]}
    skills = {"lang": ["Languages", "Python, Go"], "data": ["Data", "Kafka, Redis"]}
    spec = {"roles": [["acme", ["acme_1", "acme_2"]]], "skills": ["lang", "data"]}
    want = ["python", "kafka", "redis", "rust"]
    hits = lambda t: {w for w in want if w in t.lower()}
    jd = "We use Kafka heavily. Kafka, Python and Redis. Rust is a plus."
    n = compose.cover_note("Senior Backend Engineer (Remote)", "Initech", jd, spec, want, facts, roles, skills, hits)
    assert n.startswith("I'm applying for the Backend Engineer role at Initech: the posting's focus on Kafka")
    assert "At Acme Corp, I built Kafka pipelines in Python." in n and "I also cut p95 latency" in n
    assert "Rust" not in n and "hiring loop" not in n
    assert compose.role_name("Mid-level Full Stack Developer (Java/Spring)") == "Full Stack Developer"  # no JD term the resume lacks, no fact the resume didn't pick
