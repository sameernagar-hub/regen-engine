"""Quick start (NEXT_STEPS 6): resume skills, gate reasons and ranking, with no network and no files written."""
import datetime

from engine import try_it

NOW = datetime.datetime(2026, 11, 9, tzinfo=datetime.timezone.utc)
RESUME = "Built REST APIs in Flask on Postgres; trained PyTorch models; React front end. Two years ago."


def job(title, posted="2026-11-08T00:00:00Z", company="Acme", location="Remote - US"):
    return {"title": title, "posted": posted, "company": company, "location": location, "url": "u", "id": title}


def test_skills_need_resume_words():
    have = try_it.skills(RESUME)
    assert {"backend", "ai / ml", "frontend"} <= set(have)
    assert "go" not in have["backend"]  # "ago" is not Go
    assert "cloud / devops" not in have


def test_rank_gives_reasons_and_never_claims_missing_skills():
    have = try_it.skills(RESUME)
    jobs = [job("Software Engineer, Backend"), job("Machine Learning Engineer", posted="2026-11-01T00:00:00Z"),
            job("Senior Software Engineer"), job("Software Engineer, Kubernetes"),
            job("Software Engineer", posted="2026-09-01T00:00:00Z"), job("Software Engineer", location="London, UK"),
            job("Account Executive")]
    passed, blocked = try_it.rank(jobs, have, now=NOW, days=14)
    assert [j["title"] for _, j, _ in passed] == ["Software Engineer, Backend", "Machine Learning Engineer"]
    assert "backend" in passed[0][2] and "posted 1 d ago" in passed[0][2]
    assert blocked == {"level/title excluded": 1, "resume does not show this role's skills": 1,
                       "older than 14 days": 1, "non-US": 1, "title": 1}


def test_txt_resume_needs_no_dependency(tmp_path):
    p = tmp_path / "r.txt"
    p.write_text(RESUME, encoding="utf-8")
    assert "Flask" in try_it.resume_text(str(p))
