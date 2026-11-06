"""JD keyword line (11-05, user request): every technology / practice the posting names goes on the resume.

The user asked that all the posting's keywords appear on the page and said they will defend each one. Terms the
Fact Bank already shows are left to the normal skills lines; the rest go on one "Role Keywords" line. The line is
recorded in the spec (spec["jd_keywords"]) and in the resume event, so it is always visible which words came from
the JD rather than from the Fact Bank. Off with REGEN_JD_KEYWORDS=0.

  extract(jd)            known technical terms the JD mentions, in the JD's order of first mention
  missing(jd, page_text) the ones the rest of the page does not show yet
"""
import os
import re

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


def enabled():
    return os.environ.get("REGEN_JD_KEYWORDS", "1") != "0"


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
             "ESPP", "SVP", "EVP", "II", "III", "IV", "NA", "EU", "UK", "APAC", "EMEA", "AM", "PM", "W2", "H1B"}


def _toolish(jd):
    text = " ".join(re.sub(r"<[^>]+>", " ", __import__("html").unescape(jd or "")).split())
    out = []
    for m in _TOOLISH.finditer(text):
        w = m.group(0)
        if w not in _NOT_TECH and w.upper() not in _NOT_TECH and w not in out:
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
