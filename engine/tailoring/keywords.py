"""JD keyword line (11-05, user request): every technology / practice the posting names goes on the resume.

The user asked that all the posting's keywords appear on the page and said they will defend each one. Terms the
Fact Bank already shows are left to the normal skills lines; the rest go on one "Role Keywords" line. The line is
recorded in the spec (spec["jd_keywords"]) and in the resume event, so it is always visible which words came from
the JD rather than from the Fact Bank.

Off by default since 11-09 (user decision, docs/NEXT_STEPS.md §1.1): the terms are not Fact Bank entries and
resume.validate() cannot check them, so the README's "every resume line comes from your Fact Bank" holds only with the
line off. It is the user's choice at every engine start (11-09): `python -m engine keywords on|off` (or
REGEN_JD_KEYWORDS=1/0, which wins); a clean stop switches it back off. tests/test_truth_claims.py keeps the docs and
this default in step.

  extract(jd)            known technical terms the JD mentions, in the JD's order of first mention
  missing(jd, page_text) the ones the rest of the page does not show yet
"""
import json
import os
import re
import time

from engine.config import WORKSPACE
from engine.tailoring.compose import plain

# Canonical spelling -> extra patterns that count as a mention. Technical terms only: no soft skills, no titles.
TECH = {
    # languages
    "Python": [], "Java": [r"java(?!script)"], "JavaScript": [], "TypeScript": [], "Go": [r"golang"], "Rust": [],
    "C++": [r"c\+\+"], "C": [r"\bc(?= programming| language|/c\+\+|,)"], "C#": [r"c#"], "Kotlin": [], "Scala": [],
    "Swift": [], "Ruby": [], "PHP": [], "SQL": [], "Bash": [r"shell scripting"], "R": [r"\br(?= programming| language)"],
    "CUDA": [], "Verilog": [], "SystemVerilog": [], "VHDL": [], "MATLAB": [], "Lua": [], "Elixir": [], "Haskell": [],
    # web / backend
    "React": [r"react\.?js"], "Next.js": [r"nextjs"], "Vue.js": [r"\bvue\b"], "Angular": [], "Svelte": [],
    "Node.js": [r"node\.?js|\bnode\b"], "Express": [r"express\.?js"], "Django": [], "Flask": [], "FastAPI": [],
    "Spring Boot": [r"spring"], ".NET": [r"\.net\b|asp\.net"], "Rails": [r"ruby on rails"], "GraphQL": [], "gRPC": [],
    "REST APIs": [r"\brest(ful)?\b"], "WebSockets": [r"websocket"], "Microservices": [r"microservice"],
    "Distributed Systems": [r"distributed system"], "Event-Driven Architecture": [r"event[- ]driven"],
    "System Design": [], "API Design": [], "OAuth": [], "HTML": [], "CSS": [], "Tailwind CSS": [r"tailwind"],
    "Redux": [], "Webpack": [], "Vite": [], "Jest": [], "Cypress": [], "Playwright": [], "Selenium": [], "PyTest": [r"pytest"],
    "JUnit": [],
    # data
    "PostgreSQL": [r"postgres"], "MySQL": [], "MongoDB": [], "Redis": [], "Cassandra": [], "DynamoDB": [],
    "Elasticsearch": [r"elastic ?search|opensearch"], "Kafka": [], "RabbitMQ": [], "Spark": [r"pyspark|apache spark"],
    "Airflow": [], "dbt": [r"\bdbt\b"], "Snowflake": [], "BigQuery": [], "Redshift": [], "Databricks": [],
    "Hadoop": [], "Flink": [], "ETL": [r"\belt\b"], "Data Pipelines": [r"data pipeline"], "Data Modeling": [],
    "Pandas": [], "NumPy": [], "SQLite": [], "Supabase": [], "Firebase": [],
    # cloud / infra
    "AWS": [r"amazon web services"], "GCP": [r"google cloud"], "Azure": [], "Kubernetes": [r"k8s"], "Docker": [],
    "Terraform": [], "Helm": [], "Ansible": [], "CI/CD": [r"continuous (integration|delivery|deployment)"],
    "GitHub Actions": [], "Jenkins": [], "GitLab CI": [r"gitlab"], "Linux": [r"unix"], "Git": [], "Nginx": [],
    "Serverless": [r"lambda"], "Prometheus": [], "Grafana": [], "Datadog": [], "OpenTelemetry": [],
    "Observability": [r"monitoring|alerting|logging"], "Infrastructure as Code": [r"\biac\b"], "Networking": [r"tcp/ip"],
    "Load Balancing": [r"load balanc"], "Caching": [r"\bcache|caching"], "Concurrency": [r"multithread|multi-thread"],
    "Performance Optimization": [r"performance tuning|latency"], "Scalability": [r"scalab"], "High Availability": [],
    "Security": [r"secure coding|appsec"], "Incident Response": [r"on-?call"],
    # AI / ML
    "Machine Learning": [], "Deep Learning": [], "LLMs": [r"large language model|\bllm"], "Generative AI": [r"genai|gen ai"],
    "RAG": [r"retrieval[- ]augmented"], "AI Agents": [r"agentic|\bagents?\b"], "Prompt Engineering": [],
    "Fine-Tuning": [r"fine[- ]tun"], "Embeddings": [], "Vector Databases": [r"vector (db|database|search|store)|pinecone|pgvector|weaviate|chroma"],
    "PyTorch": [], "TensorFlow": [], "JAX": [], "scikit-learn": [r"sklearn"], "Hugging Face": [r"huggingface|transformers"],
    "LangChain": [], "LlamaIndex": [], "OpenAI API": [r"openai"], "MLOps": [], "Model Evaluation": [r"evals?\b|evaluation"],
    "Computer Vision": [r"opencv"], "NLP": [r"natural language processing"], "Reinforcement Learning": [],
    "Model Serving": [r"inference"], "Recommendation Systems": [r"recommend"], "Statistics": [],
    # hardware / systems
    "Embedded Systems": [r"embedded"], "Firmware": [], "RTOS": [], "Microcontrollers": [r"microcontroller|\bmcu"],
    "ARM": [r"\barm\b|cortex-m"], "FPGA": [], "Operating Systems": [r"kernel"], "Compilers": [r"compiler"],
    "Computer Architecture": [], "GPU Programming": [r"\bgpu"], "I2C": [], "SPI": [r"\bspi\b"], "UART": [],
    "CAN Bus": [r"\bcan bus|\bcan\b protocol"], "ROS": [r"\bros2?\b"], "Robotics": [], "Device Drivers": [r"driver"],
    # practice
    "Agile": [r"scrum"], "Unit Testing": [r"unit test"], "Integration Testing": [r"integration test"], "TDD": [r"test[- ]driven"],
    "Code Review": [], "Debugging": [], "Data Structures": [], "Algorithms": [], "Object-Oriented Design": [r"\boop\b|object[- ]oriented"],
    "Mobile Development": [r"react native"], "A/B Testing": [r"a/b test|experimentation"],
}

_RX = {}
for name, extra in TECH.items():
    pats = [r"(?<![a-z0-9+#.])" + re.escape(name.lower()) + r"(?![a-z0-9+#])"] + extra
    _RX[name] = re.compile("|".join(f"(?:{p})" for p in pats))


DEFAULT = "0"  # off unless the user switches it on for a run (see the module note)
PATH = os.path.join(WORKSPACE, "keywords.json")


def arm(url):
    """The A/B arm of one posting (NEXT_STEPS §3): "on" or "off" from a hash of its URL without the query string, so
    the same posting always lands in the same arm (a retry rebuilding its PDF too) and arms are ~50/50. O(len(url))."""
    import hashlib
    key = (url or "").split("?")[0].split("#")[0].rstrip("/").lower()
    return "on" if hashlib.sha256(key.encode()).digest()[0] % 2 else "off"


def ab_active():
    from engine import targeting
    return bool(targeting.load().get("keywords_ab")) and os.environ.get("REGEN_JD_KEYWORDS") not in ("0", "1")


def enabled(url=None):
    """Whether this resume gets the line. REGEN_JD_KEYWORDS (0/1) wins when set; else, while the A/B is on
    (profile/targeting.json keywords_ab) and the posting URL is known, its arm decides; else the per-run switch
    workspace/keywords.json, which every container reads live (pipeline, answers, appliers), so one
    `engine keywords on|off` covers the whole stack; else off."""
    env = os.environ.get("REGEN_JD_KEYWORDS")
    if env in ("0", "1"):
        return env == "1"
    if url and ab_active():
        return arm(url) == "on"
    try:
        return json.load(open(PATH, encoding="utf-8")).get("on") is True
    except (OSError, ValueError, AttributeError):  # no file or a broken one: the safe answer is the default, off
        return DEFAULT == "1"


def switch(on, by="operator"):
    """Write the choice atomically and record a `keywords` event, so the ledger shows which runs had the line."""
    state = {"on": bool(on), "set_at": time.strftime("%Y-%m-%d %H:%M:%S"), "by": by}
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, PATH)
    from engine.feedback.events import record
    record("keywords", on=state["on"], by=by)
    return state


def main(argv):
    """python -m engine keywords [on|off]: the user's choice at each engine start; no argument shows it."""
    if argv:
        if argv[0] not in ("on", "off"):
            raise SystemExit("usage: python -m engine keywords [on|off]")
        switch(argv[0] == "on")
    src = "REGEN_JD_KEYWORDS" if os.environ.get("REGEN_JD_KEYWORDS") in ("0", "1") else "workspace/keywords.json"
    print(f"Role Keywords line: {'ON' if enabled() else 'off'} ({src}; off is the default, chosen by the user per run)")
    if ab_active():
        print("  A/B is ON (profile/targeting.json keywords_ab): each posting's URL hash picks on/off, overriding the switch above")


def extract(jd):
    low = plain(jd)
    found = [(m.start(), name) for name, rx in _RX.items() if (m := rx.search(low))]
    return [name for _, name in sorted(found)]


# Tool-like words outside TECH (user 11-05: "everything that a JD has"): acronyms (SOC2, ETL), CamelCase (OpenSearch),
# dotted / plus names (Vue.js, C++). Common non-technical acronyms and words are dropped.
_TOOLISH = re.compile(r"(?<![\w.])(?:[A-Z]{2,6}\d?|[A-Z][a-z]+[A-Z][A-Za-z]+|[A-Za-z]+\.(?:js|io|ai|net)|[A-Z][a-z]+(?:DB|QL|MQ))(?![\w])")
_NOT_TECH = {"US", "USA", "EEO", "EOE", "PTO", "HR", "CEO", "CTO", "VP", "OPT", "CPT", "FAQ", "LLC", "INC", "NYC", "SF", "LA",
             "UTC", "PST", "EST", "PT", "ET", "MS", "BS", "BA", "PHD", "GPA", "AND", "OR", "THE", "OUR", "YOU", "WE", "ADA",
             "DEI", "LGBTQ", "LinkedIn", "YouTube", "TikTok", "COVID", "IRS", "TBD", "ASAP", "FTE", "OTE", "RSU", "RSUs",
             "ESPP", "SVP", "EVP", "II", "III", "IV", "NA", "EU", "UK", "APAC", "EMEA", "AM", "PM", "W2", "H1B",
             # 11-12: legal / benefits / EEO boilerplate seen on the Role Keywords line
             "SDE", "CCPA", "GDPR", "AD", "EAP", "USD", "VEVRAA", "EAD", "EEOC", "OFCCP", "FMLA", "HSA", "FSA", "PPO", "HMO",
             "SMS", "QA", "IT", "AI", "ML", "UI", "UX", "IDE", "YOUR", "SWE", "SDET", "TBA", "DOE", "LLNL", "CFR", "ITAR",
             "EAR", "HIPAA", "PII", "PHI", "SOX", "ADEA", "GINA", "USERRA", "DUTIES", "KEY", "DAY"}


# 11-12: state codes and all-caps section headings ("KEY DUTIES", "DAY IN THE LIFE") were landing on the Role Keywords
# line and counting as skills the bank lacks (MN, WI, DUTIES, KEY, DAY seen on real postings)
_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK "
              "OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
_HEADING = re.compile(r"(?<![A-Za-z])[A-Z]{2,}[\s&/:-]+[A-Z]{2,}(?![A-Za-z])")  # whole caps words, no comma lists


def _toolish(jd):
    text = " ".join(re.sub(r"<[^>]+>", " ", __import__("html").unescape(jd or "")).split())
    out = []
    for m in _TOOLISH.finditer(text):
        w = m.group(0)
        if w in _NOT_TECH or w.upper() in _NOT_TECH or w in _STATES or w in out:
            continue
        if w.isupper() and not any(c.isdigit() for c in w):
            ctx = text[max(0, m.start() - 12):m.end() + 12]
            if _HEADING.search(ctx) and w.lower() not in {t.lower() for t in TECH}:  # part of an all-caps heading
                continue
        out.append(w)
    return out


def missing(jd, page_text, limit=None):
    """Every JD term the page doesn't show yet (TECH patterns, then tool-like words), JD order. No cap by default."""
    page = " ".join(re.sub(r"<[^>]+>", " ", page_text).split()).lower()
    low = plain(jd)
    out = []
    for t in extract(jd):
        if _RX[t].search(page):
            continue
        m = _RX[t].search(low).group(0).strip()  # the JD's own spelling goes on too ("Elasticsearch (OpenSearch)")
        out.append(t if m.lower() in t.lower() or len(m) < 3 else f"{t} ({m})")
    have = {t.lower() for t in out} | {t.lower() for t in extract(jd)}
    for w in _toolish(jd):
        lw = w.lower()
        if lw not in have and not re.search(r"(?<![a-z0-9])" + re.escape(lw) + r"(?![a-z0-9])", page) \
                and not any(_RX[t].search(lw) for t in TECH):
            out.append(w)
            have.add(lw)
    return out[:limit] if limit else out
