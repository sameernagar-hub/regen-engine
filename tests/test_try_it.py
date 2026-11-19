"""Quick start / Test drive: the resume decides the roles (lane, level, JD keywords), with no network and no files."""
import datetime

from engine import try_it

NOW = datetime.datetime(2026, 11, 9, tzinfo=datetime.timezone.utc)
ENGINEER = """Software Engineer with 4+ years. Python, FastAPI, PostgreSQL, React, TypeScript, Docker, AWS, Kafka.
Software Engineer II | Acme | 2022 - Present. Built REST APIs and microservices."""
PM = """Senior Product Manager with 5+ years. Roadmapping, go-to-market, A/B testing, SQL, Mixpanel, Jira, PRDs.
Product Manager | Acme | 2020 - Present. Owned checkout and payments; ran user interviews."""
JD = {"backend": "<p>You will build REST APIs and microservices in Python and Go on AWS with Kafka. 3+ years.</p>",
      "pm": "<p>Own the roadmap and go-to-market. Run A/B testing with SQL and Mixpanel. 5+ years.</p><p>Benefits include healthcare.</p>",
      "ios": "<p>Swift, iOS.</p>"}


def job(title, jd="backend", posted="2026-11-08T00:00:00Z", company="Acme", location="Remote - US"):
    return {"title": title, "posted": posted, "company": company, "location": location, "url": f"u/{title}", "jd": jd}


JOBS = [job("Software Engineer, Backend"), job("Senior Product Manager, Payments", "pm", company="Beta"),
        job("Staff Software Engineer"), job("Software Engineer, iOS", "ios"), job("Product Designer"),
        job("Software Engineer", posted="2026-08-01T00:00:00Z"), job("Software Engineer", location="London, UK"),
        job("Manager II, Software Engineering")]
fetch = lambda j: JD[j["jd"]]


def test_profile_reads_lane_years_and_level():
    e, p = try_it.profile(ENGINEER), try_it.profile(PM)
    assert e["lanes"][0] == "software" and e["years"] == 4 and not e["senior"]
    assert p["lanes"][0] == "product" and p["years"] == 5 and p["senior"]
    assert "Go" not in p["keywords"]  # go-to-market is not the Go language


def test_different_resumes_get_different_roles():
    e = try_it.rank(JOBS, ENGINEER, now=NOW, fetch=fetch)
    p = try_it.rank(JOBS, PM, now=NOW, fetch=fetch)
    assert [j["title"] for j in e["top"]] == ["Software Engineer, Backend"]
    assert [j["title"] for j in p["top"]] == ["Senior Product Manager, Payments"]
    assert e["blocked"]["level: staff / principal level"] == 1 and e["blocked"]["outside the US"] == 1
    assert e["blocked"]["level: people-manager role"] == 1 and e["blocked"]["specialty the resume doesn't show"] == 1


def test_reason_is_ats_style_and_ignores_boilerplate():
    top = try_it.rank(JOBS, PM, now=NOW, fetch=fetch)["top"][0]
    assert top["reason"].startswith("ATS match ") and "Roadmapping" in top["matched"] and "Go-to-Market" in top["matched"]
    assert not any("health" in m.lower() for m in top["missing"])  # the benefits paragraph is not a requirement
    eng = try_it.rank(JOBS, ENGINEER, now=NOW, fetch=fetch)["top"][0]
    assert "Go" in eng["missing"] and "asks 3+ yrs, resume shows 4" in eng["reason"]


def test_txt_resume_needs_no_dependency(tmp_path):
    p = tmp_path / "r.txt"
    p.write_text(ENGINEER, encoding="utf-8")
    assert "FastAPI" in try_it.resume_text(str(p))


SALES = """Senior Account Executive with 5+ years of B2B SaaS sales closing mid-market and enterprise deals; MEDDIC,
Challenger Sale, cold outbound prospecting, contract negotiation, multi-threading complex accounts with C-level buyers.
Senior Account Executive | Veloce Cloud Software | 2024 - Present. Achieved 132% of quota; managed full-cycle sales
for workflow automation software. Sales Development Representative (SDR) | Acme | 2021 - 2022. Exceeded monthly SQL
quota for 11 consecutive months. Salesforce CRM, HubSpot, Gong. President's Club 2025."""


def test_sales_resume_reads_as_sales_not_software():
    # 11-18: "Software" in an employer's name and in the product sold made an Account Executive read as "software"
    p = try_it.profile(SALES)
    assert p["lanes"] == ["sales"]
    assert not {"C", "SQL", "Concurrency"} & set(p["keywords"])  # C-level, SQL quota, multi-threading accounts
    assert {"MEDDIC", "Salesforce", "Negotiation"} <= set(p["keywords"])
    jobs = [job("Enterprise Account Executive", "pm"), job("Software Engineer, Backend")]
    assert [j["title"] for j in try_it.rank(jobs, SALES, now=NOW, fetch=fetch)["top"]] == ["Enterprise Account Executive"]
