"""Resume classifier for the Test drive: what kind of role does this resume do?

A pipeline, not a pile of regexes, so the answer holds for any resume in the world, not only software ones:

  1. tokenize   Unicode-normalize, keep tech tokens whole (C++, C#, .NET, Node.js), split on everything else, expand
                abbreviations ("k8s" -> kubernetes, "RN" -> registered nurse, "SDR" -> sales development representative).
  2. normalize  drop stopwords, then one fixed suffix stemmer (plural, -ing, -ed, final e), with a short list of words
                kept whole because stemming would merge two meanings ("accounting" is not "accounts").
  3. structure  find the sections (summary, experience, skills, education, ...) and the role lines inside them. On a
                role line ("Senior Account Executive | Veloce Cloud Software | Chicago") only the TITLE counts: the
                employer and the place carry no weight, so a salesperson at a software company is a salesperson. The
                newest role weighs most (career changers are read by what they do now).
  4. features   longest-first phrase matching of each family's vocabulary (4-grams down to single stems), so
                "sales engineer" is one solutions phrase, not "sales" + "engineer".
  5. classify   each phrase adds weight x its specificity (1 / how many families use it, the IDF idea); a family's
                score is then blended with the cosine between the resume's phrase vector and the family's centroid
                (nearest-centroid classification). Output: a primary label, secondary labels for a hybrid profile,
                probabilities, a confidence, and the evidence phrases. Too little evidence -> "unclassified": the
                engine says it can't tell instead of guessing software.

The same classifier reads posting titles (classify_title), so a resume and a job are labelled from one taxonomy.
apps/web/lib/resume-nlp.ts is a line-for-line port; scripts/try_rules.py exports the data below to the web, and
tests/test_resume_nlp.py checks both on a corpus of different resumes. Pure Python, no packages, nothing stored.
"""
import math, re, unicodedata

# ---- the taxonomy: families of roles. titles = role names (strong), terms = the work and tools (weak) ----
FAMILIES = {
    "software": {
        "titles": ["engineering manager", "software engineering manager", "engineering lead", "tech lead", "software engineer", "software developer", "software development engineer", "backend engineer",
                   "frontend engineer", "full stack engineer", "full stack developer", "web developer", "mobile developer",
                   "ios engineer", "android engineer", "application developer", "programmer", "platform engineer",
                   "product engineer", "founding engineer", "member of technical staff", "api engineer", "game developer",
                   "backend developer", "frontend developer", "software engineering intern", "developer"],
        "terms": ["microservice", "rest api", "graphql", "backend", "frontend", "full stack", "react", "angular", "vue",
                  "node js", "django", "flask", "fastapi", "spring boot", "java", "javascript", "typescript", "golang",
                  "rust", "c plus plus", "c sharp", "dot net", "kotlin", "swift", "ruby on rails", "php", "git",
                  "ci cd", "unit test", "code review", "object oriented", "data structure", "algorithm", "api",
                  "web application", "mobile app", "system design", "computer science", "python", "postgresql", "mysql", "mongodb", "redis", "html", "css"]},
    "ai / ml": {
        "titles": ["machine learning engineer", "ml engineer", "ai engineer", "applied scientist", "research scientist",
                   "deep learning engineer", "computer vision engineer", "nlp engineer", "machine learning scientist",
                   "genai engineer", "llm engineer", "ai researcher"],
        "terms": ["machine learning", "deep learning", "pytorch", "tensorflow", "model training", "fine tuning", "llm",
                  "large language model", "rag", "retrieval augmented generation", "embedding", "transformer",
                  "computer vision", "natural language processing", "reinforcement learning", "neural network",
                  "scikit learn", "hugging face", "mlops", "inference", "generative ai", "vector search"]},
    "data": {
        "titles": ["data engineer", "data scientist", "data analyst", "analytics engineer", "business intelligence analyst",
                   "bi developer", "bi analyst", "business analyst", "quantitative analyst", "statistician",
                   "data architect", "database administrator"],
        "terms": ["sql", "etl", "data pipeline", "data warehouse", "dbt", "airflow", "spark", "snowflake", "bigquery",
                  "redshift", "tableau", "power bi", "looker", "pandas", "statistics", "regression", "ab testing",
                  "dashboard", "data model", "data visualization", "kafka", "hadoop", "r programming"]},
    "devops / sre": {
        "titles": ["incident manager", "enterprise architect", "devops engineer", "site reliability engineer", "infrastructure engineer", "cloud engineer",
                   "production engineer", "reliability engineer", "systems engineer", "system administrator",
                   "network engineer", "cloud architect", "build engineer", "release engineer"],
        "terms": ["kubernetes", "terraform", "docker", "ansible", "aws", "azure", "gcp", "observability", "prometheus",
                  "grafana", "incident response", "on call", "helm", "linux", "infrastructure as code", "load balancer",
                  "networking", "uptime", "sla", "monitoring", "jenkins", "github actions"]},
    "security": {
        "titles": ["grc engineer", "threat intelligence engineer", "security operations engineer", "trust and safety analyst", "security engineer", "security analyst", "application security engineer", "penetration tester",
                   "soc analyst", "information security analyst", "cybersecurity analyst", "security architect",
                   "detection engineer", "threat analyst"],
        "terms": ["penetration testing", "threat model", "vulnerability", "siem", "soc", "incident handling",
                  "owasp", "iam", "zero trust", "malware", "forensics", "firewall", "cissp", "security plus", "nist",
                  "iso 27001", "encryption", "appsec", "red team", "blue team"]},
    "hardware / embedded": {
        "titles": ["embedded engineer", "embedded software engineer", "firmware engineer", "hardware engineer",
                   "fpga engineer", "asic engineer", "electrical engineer", "pcb designer", "verification engineer",
                   "test engineer", "validation engineer", "silicon engineer"],
        "terms": ["firmware", "embedded", "rtos", "microcontroller", "fpga", "verilog", "vhdl", "asic", "pcb", "uvm",
                  "oscilloscope", "circuit", "schematic", "semiconductor", "arm cortex", "i2c", "spi", "uart",
                  "signal processing", "altium"]},
    "product": {
        "titles": ["product manager", "product owner", "group product manager", "technical product manager",
                   "senior product manager", "product lead", "associate product manager", "head of product"],
        "terms": ["roadmap", "product strategy", "product requirement", "prd", "user research", "go to market",
                  "product discovery", "okr", "feature prioritization", "product analytics", "mixpanel", "amplitude",
                  "product launch", "backlog", "user stories", "product vision", "market research"]},
    "design": {
        "titles": ["user researcher", "design researcher", "product designer", "ux designer", "ui designer", "ux researcher", "interaction designer",
                   "visual designer", "graphic designer", "design lead", "web designer", "motion designer",
                   "user experience designer", "brand designer", "illustrator"],
        "terms": ["figma", "sketch", "wireframe", "prototype", "design system", "usability testing", "user flow",
                  "adobe illustrator", "photoshop", "indesign", "typography", "user interface", "visual design",
                  "accessibility", "persona", "journey map", "after effects"]},
    "program / project": {
        "titles": ["program manager", "project manager", "technical program manager", "scrum master", "delivery manager",
                   "project coordinator", "pmo analyst", "agile coach"],
        "terms": ["project management", "program management", "project management professional", "stakeholder",
                  "risk register", "gantt", "scope", "milestone", "jira", "agile", "scrum", "waterfall", "budget tracking",
                  "status report", "cross functional", "dependency", "kanban", "sprint planning"]},
    "solutions / sales engineering": {
        "titles": ["solutions consultant", "implementation consultant", "implementation architect", "deployment strategist", "solutions engineer", "sales engineer", "solutions architect", "forward deployed engineer",
                   "customer engineer", "pre sales engineer", "technical account manager", "implementation engineer",
                   "field engineer"],
        "terms": ["proof of concept", "technical demo", "pre sales", "rfp", "customer deployment",
                  "technical discovery", "solution design", "customer integration"]},
    "sales": {
        "titles": ["account development representative", "sales leader", "sales development manager", "enterprise sales manager", "account director", "client partner", "partner manager", "channel manager", "account executive", "sales development representative", "business development representative",
                   "account manager", "sales manager", "sales representative", "business development manager",
                   "sales associate", "inside sales", "regional sales manager", "sales director", "partnerships manager",
                   "enterprise account executive", "sales consultant", "territory manager"],
        "terms": ["quota", "closed won", "pipeline generation", "qualified pipeline", "prospecting", "cold call",
                  "outbound", "meddic", "challenger sale", "sandler", "negotiation", "upsell", "cross sell", "arr",
                  "annual recurring revenue", "president club", "sales cycle", "deal", "crm", "salesforce", "hubspot",
                  "gong", "zoominfo", "sales navigator", "sales qualified", "book of business", "commission",
                  "lead generation", "territory", "full cycle sales", "account expansion"]},
    "marketing": {
        "titles": ["marketing manager", "digital marketing manager", "growth marketer", "content marketer",
                   "content strategist", "brand manager", "product marketing manager", "marketing coordinator",
                   "social media manager", "seo specialist", "demand generation manager", "marketing specialist",
                   "communications manager", "public relations"],
        "terms": ["campaign", "seo", "sem", "content marketing", "demand generation", "email marketing", "marketing automation",
                  "google analytics", "paid social", "paid search", "brand strategy", "social media", "copywriting",
                  "marketo", "conversion rate", "ctr", "cac", "positioning", "messaging", "press release", "influencer"]},
    "customer success / support": {
        "titles": ["customer success manager", "customer support specialist", "support engineer", "customer service representative",
                   "technical support engineer", "help desk", "client services", "onboarding specialist",
                   "implementation manager", "customer experience", "call center"],
        "terms": ["customer satisfaction", "csat", "nps", "renewal", "churn", "net revenue retention", "zendesk",
                  "ticket", "escalation", "customer onboarding", "first response", "knowledge base", "service level",
                  "customer health", "intercom"]},
    "finance / accounting": {
        "titles": ["investor relations", "corporate development", "payments analyst", "accountant", "staff accountant", "senior accountant", "financial analyst", "controller",
                   "auditor", "bookkeeper", "tax associate", "investment banking analyst", "fp a analyst",
                   "finance manager", "accounts payable", "accounts receivable", "treasury analyst", "actuary",
                   "certified public accountant", "credit analyst", "portfolio manager", "chief financial officer"],
        "terms": ["gaap", "ifrs", "general ledger", "reconciliation", "accounting", "month end close", "financial statement",
                  "budgeting", "forecasting", "variance analysis", "quickbooks", "netsuite", "sap", "audit", "tax return",
                  "financial model", "valuation", "dcf", "accrual", "journal entries", "sox", "cpa", "cfa"]},
    "healthcare": {
        "titles": ["registered nurse", "nurse", "nurse practitioner", "licensed practical nurse", "physician",
                   "medical assistant", "physical therapist", "pharmacist", "pharmacy technician", "dental hygienist",
                   "certified nursing assistant", "emergency medical technician", "paramedic", "occupational therapist",
                   "radiologic technologist", "clinical research coordinator", "medical doctor", "surgeon",
                   "caregiver", "home health aide", "respiratory therapist", "phlebotomist"],
        "terms": ["patient care", "patient", "clinical", "hospital", "icu", "emr", "ehr", "epic", "vital sign",
                  "medication administration", "bls", "acls", "hipaa", "triage", "nursing", "telemetry", "bedside",
                  "care plan", "rehabilitation", "diagnosis", "treatment", "surgery", "pediatric", "oncology", "cpr"]},
    "education": {
        "titles": ["teacher", "high school teacher", "elementary teacher", "professor", "lecturer", "tutor",
                   "instructor", "teaching assistant", "school principal", "school counselor", "special education teacher",
                   "curriculum developer", "instructional designer", "academic advisor", "substitute teacher",
                   "teaching associate"],
        "terms": ["lesson plan", "curriculum", "classroom", "student engagement", "student achievement", "grading", "pedagogy", "classroom management",
                  "iep", "differentiated instruction", "teaching", "syllabus", "lecture", "learning objective",
                  "teaching certification", "parent teacher", "standardized test"]},
    "legal": {
        "titles": ["attorney", "lawyer", "paralegal", "legal assistant", "associate attorney", "counsel",
                   "general counsel", "law clerk", "compliance officer", "contract manager", "legal counsel"],
        "terms": ["litigation", "contract drafting", "legal research", "westlaw", "lexisnexis", "deposition", "brief",
                  "bar admission", "juris doctor", "regulatory compliance", "due diligence", "intellectual property",
                  "discovery motion", "court filing", "case management", "statute"]},
    "people / hr": {
        "titles": ["recruiter", "technical recruiter", "talent acquisition", "hr generalist", "hr manager",
                   "human resources manager", "people partner", "hr business partner", "sourcer",
                   "talent acquisition partner", "people operations", "compensation analyst", "hr coordinator"],
        "terms": ["sourcing", "full cycle recruiting", "candidate", "offer letter", "headcount", "onboarding",
                  "employee relations", "performance review", "hris", "workday", "benefits administration",
                  "talent pipeline", "interview loop", "hiring manager", "employer brand", "payroll", "greenhouse",
                  "applicant tracking", "human resources"]},
    "operations / supply chain": {
        "titles": ["chief of staff", "customs specialist", "freight coordinator", "operations manager", "supply chain analyst", "logistics coordinator", "procurement specialist",
                   "buyer", "warehouse manager", "operations analyst", "inventory analyst", "purchasing manager",
                   "supply chain manager", "fleet manager", "production planner", "business operations"],
        "terms": ["supply chain", "logistics", "inventory", "procurement", "vendor management", "warehouse",
                  "lean", "six sigma", "erp", "demand planning", "shipping", "fulfillment", "sourcing strategy",
                  "process improvement", "forklift", "distribution center", "purchase order"]},
    "administrative": {
        "titles": ["administrative assistant", "executive assistant", "office manager", "receptionist",
                   "office administrator", "data entry clerk", "secretary", "administrative coordinator",
                   "virtual assistant", "front desk"],
        "terms": ["calendar management", "scheduling", "data entry", "filing", "travel arrangement", "microsoft office",
                  "meeting minutes", "phone support", "correspondence", "office supplies", "expense report", "front office"]},
    "research / science": {
        "titles": ["research assistant", "postdoctoral researcher", "laboratory technician", "lab technician",
                   "chemist", "biologist", "research associate", "scientist", "physicist", "microbiologist",
                   "environmental scientist", "geologist"],
        "terms": ["laboratory", "experiment", "pcr", "assay", "cell culture", "peer reviewed", "publication",
                  "hypothesis", "spectroscopy", "chromatography", "grant", "thesis", "dissertation", "western blot",
                  "field research", "specimen"]},
    "engineering (non-software)": {
        "titles": ["mechanical engineer", "civil engineer", "chemical engineer", "structural engineer",
                   "manufacturing engineer", "industrial engineer", "aerospace engineer", "process engineer",
                   "quality engineer", "design engineer", "project engineer", "environmental engineer", "biomedical engineer"],
        "terms": ["autocad", "solidworks", "catia", "finite element", "cad", "gd&t", "tolerance", "manufacturing",
                  "prototype testing", "hvac", "structural analysis", "thermodynamics", "fluid", "matlab", "ansys",
                  "root cause analysis", "quality control", "iso 9001", "construction"]},
    "skilled trades": {
        "titles": ["electrician", "plumber", "carpenter", "welder", "mechanic", "hvac technician", "machinist",
                   "maintenance technician", "construction worker", "truck driver", "technician", "installer",
                   "auto mechanic", "line cook"],
        "terms": ["blueprint", "osha", "power tools", "wiring", "journeyman", "apprenticeship", "welding",
                  "preventive maintenance", "cdl", "troubleshooting equipment", "safety compliance", "forklift certified",
                  "hand tools", "installation"]},
    "hospitality / retail": {
        "titles": ["cashier", "server", "bartender", "barista", "store manager", "retail associate", "chef",
                   "cook", "host", "hotel manager", "front desk agent", "sales floor associate", "shift supervisor",
                   "restaurant manager", "housekeeper", "concierge"],
        "terms": ["point of sale", "pos", "customer service", "food safety", "merchandising", "inventory count",
                  "guest experience", "cash handling", "menu", "reservation", "food preparation", "store operations",
                  "visual merchandising", "servsafe"]},
    "creative / media": {
        "titles": ["writer", "editor", "journalist", "copywriter", "content writer", "technical writer", "video editor",
                   "photographer", "producer", "reporter", "animator", "art director", "creative director", "author"],
        "terms": ["editorial", "publishing", "storytelling", "adobe premiere", "final cut", "videography", "photography",
                  "manuscript", "byline", "ap style", "content creation", "podcast", "screenplay", "proofreading"]},
}

# ---- tokenizer data ----
STOP = set("""a an the and or but if then of to in on at by for with from as is are was were be been being this that these
those it its i me my we our you your he she they them their his her him not no nor so too very can will would should
could may might must do does did done have has had having over under into onto about across after before during
while within without per via up down out off again further once here there when where why how all any both each few
more most other some such only own same than s t just also etc using use used including include includes responsible
various new""".split())
KEEP = {"accounting", "marketing", "nursing", "teaching", "training", "pricing", "banking", "consulting",
        "manufacturing", "testing", "publishing", "sourcing", "recruiting", "staffing", "welding", "wiring", "scheduling",
        "filing", "budgeting", "forecasting", "merchandising", "onboarding", "networking", "monitoring", "litigation",
        "fulfillment", "photography", "videography", "storytelling", "copywriting", "proofreading", "prospecting"}
ALIASES = {"k8s": "kubernetes", "js": "javascript", "ts": "typescript", "ml": "machine learning", "nlp": "natural language processing",
           "llms": "llm", "genai": "generative ai", "swe": "software engineer", "sde": "software engineer",
           "sdr": "sales development representative", "sdrs": "sales development representative",
           "bdr": "business development representative", "bdrs": "business development representative",
           "rn": "registered nurse", "lpn": "licensed practical nurse", "cna": "certified nursing assistant",
           "emt": "emergency medical technician", "np": "nurse practitioner", "cpa": "certified public accountant",
           "hr": "human resources", "hrbp": "hr business partner", "sre": "site reliability engineer",
           "qa": "quality assurance", "ux": "ux", "pmp": "project management professional", "tpm": "technical program manager",
           "fp&a": "fp a", "fpa": "fp a", "b2b": "b2b", "saas": "saas", "ai": "ai", "jd": "juris doctor",
           "ehr": "ehr", "emr": "emr", "iac": "infrastructure as code", "postgres": "postgresql", "golang": "golang"}
SECTIONS = {  # header words -> section; weights below
    "summary": ["summary", "profile", "objective", "about me", "professional summary", "career summary", "about", "overview"],
    "experience": ["experience", "work experience", "professional experience", "employment", "employment history",
                   "work history", "career history", "relevant experience", "experience highlights"],
    "skills": ["skills", "technical skills", "core competencies", "competencies", "tech stack", "tools", "technologies",
               "areas of expertise", "expertise", "key skills", "qualifications", "skills and tools"],
    "education": ["education", "academic background", "academics", "education and training"],
    "projects": ["projects", "personal projects", "selected projects", "academic projects"],
    "certifications": ["certifications", "licenses", "certificates", "licenses and certifications", "credentials"],
    "awards": ["awards", "honors", "awards and recognition", "achievements", "recognition"],
    "publications": ["publications", "research", "presentations"],
    "volunteer": ["volunteer", "volunteering", "volunteer experience", "community", "leadership", "activities",
                  "interests", "hobbies"],
}
SECTION_W = {"header": 1.0, "body": 1.0, "summary": 1.0, "experience": 1.0, "skills": 1.0, "projects": 0.8, "education": 0.6,
             "certifications": 1.0, "awards": 0.3, "publications": 0.7, "volunteer": 0.25}
TITLE_W = {"title": 3.0, "summary": 1.5, "mention": 0.3}  # a title phrase on a role line / in the summary / anywhere else
RECENCY = [1.0, 0.85, 0.7, 0.6, 0.5]  # role 1 (newest) .. role 5+
MIN_EVIDENCE = 3.0      # below this the resume is "unclassified"
SECONDARY = 0.4         # another family within 40% of the top one is part of a hybrid profile
BLEND = 0.7             # final = BLEND * lexical share + (1 - BLEND) * centroid cosine share
MAX_N = 4
HEADER_LINES = 3        # the top of a resume (name, headline, contact) before any section header
BULLET = r"^\s*(?:[-*•·▪◦‣–—>]|\d{1,2}[.)])\s+"
DATE_RANGE = r"(?:19|20)\d\d\s*(?:-|–|—|to)\s*(?:(?:19|20)\d\d|present|current|now)|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(?:19|20)\d\d"
MONTHS = r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b|\b(?:present|current|now)\b"
SEGMENT = r"\s+\|\s+|\s*\|\s*|\s+[@]\s+|\s+at\s+|\s+[–—]\s+|\s+-\s+|\s*•\s*|,\s+|\t"


def fold(text):
    """Unicode -> plain lowercase ASCII-ish text, tech tokens protected so the splitter keeps them."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    t = t.replace("’", "'").replace("‘", "'")
    t = re.sub(r"c\+\+", " c plus plus ", t)
    t = re.sub(r"(?<![a-z])c#", " c sharp ", t)
    t = re.sub(r"(?<![a-z])f#", " f sharp ", t)
    t = re.sub(r"\.net\b", " dot net ", t)
    t = re.sub(r"\b([a-z]+)\.js\b", r" \1 js ", t)
    t = re.sub(r"\bci\s*/\s*cd\b", " ci cd ", t)
    t = re.sub(r"\ba\s*/\s*b\b", " ab ", t)
    t = re.sub(r"\bp\s*&\s*l\b", " pnl ", t)
    t = re.sub(r"\bfp\s*&\s*a\b", " fp a ", t)
    t = re.sub(r"\bpresident'?s\b", " president ", t)
    return t


def stem(w):
    """One fixed suffix stemmer (both languages run exactly these steps): plurals, -ing / -ed, then a final e."""
    if w in KEEP or len(w) <= 3 or not w.isalpha():
        return w
    if w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    for suf in ("ing", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 3 and re.search(r"[aeiouy]", w[:-len(suf)]):
            w = w[:-len(suf)]
            break
    if w.endswith("e") and len(w) > 4:
        w = w[:-1]
    return w


def tokens(text, stats=None):
    """fold -> split -> aliases -> stopwords -> stems. stats (a dict) collects counts for the page's pipeline view."""
    raw = [t for t in re.split(r"[^a-z0-9+#&]+", fold(text)) if t]
    out = []
    for t in raw:
        t = t.strip("&")
        if not t or t.isdigit():
            continue
        words = ALIASES.get(t, t).split()
        if stats is not None and t in ALIASES and ALIASES[t] != t:
            stats["aliases"] = stats.get("aliases", 0) + 1
        for w in words:
            if w in STOP or (len(w) == 1 and w not in ("c", "r")):
                if stats is not None:
                    stats["stopwords"] = stats.get("stopwords", 0) + 1
                continue
            out.append(stem(w))
    if stats is not None:
        stats["raw"] = stats.get("raw", 0) + len(raw)
    return out


def phrase_key(phrase):
    return " ".join(tokens(phrase))


def _index():
    """phrase key -> [(family, kind)], plus each phrase's specificity (1 / families using it) and the centroids."""
    idx = {}
    for fam, d in FAMILIES.items():
        for kind in ("titles", "terms"):
            for p in d[kind]:
                k = phrase_key(p)
                if k and (fam, kind) not in idx.setdefault(k, []):
                    idx[k].append((fam, kind))
    spec = {k: 1.0 / len({f for f, _ in v}) for k, v in idx.items()}
    cent = {f: {} for f in FAMILIES}
    for k, v in idx.items():
        for f, kind in v:
            cent[f][k] = max(cent[f].get(k, 0), (TITLE_W["title"] if kind == "titles" else 1.0) * spec[k])
    return idx, spec, cent


INDEX, SPEC, CENTROID = _index()


def match(toks):
    """Longest-first phrase matching: [(phrase key, [(family, kind)])], each token used once."""
    out, i, n = [], 0, len(toks)
    while i < n:
        for size in range(min(MAX_N, n - i), 0, -1):
            k = " ".join(toks[i:i + size])
            if k in INDEX:
                out.append((k, INDEX[k]))
                i += size
                break
        else:
            i += 1
    return out


def section_of(line):
    """The section a header line opens, or None. A header is short and is (or starts with) a known section name."""
    t = " ".join(re.sub(r"[^a-z& ]+", " ", fold(line)).replace("&", " and ").split())
    if not t or len(t.split()) > 5:
        return None
    for sec, names in SECTIONS.items():
        for name in names:
            if t == name or (t.startswith(name + " ") and len(t.split()) <= len(name.split()) + 2):
                return sec
    return None


def split_lines(text):
    """Lines, with pasted one-line resumes split at bullets and header words so the structure step still has rows."""
    lines = [l for l in re.split(r"\r?\n", text or "") if l.strip()]
    if len(lines) < 4:
        lines = [l for part in lines for l in re.split(r"\s+(?=[•▪◦‣]\s)|\s+(?=\*\s)|\s+(?=-\s[A-Z])", part) if l.strip()]
    return lines


def role_title(line, section):
    """The title segment of a role line ("Title | Company | City", "Title at Company", "Title, Company"), else None."""
    if re.match(BULLET, line) or section not in ("experience", "body", "header", "projects", "volunteer"):
        return None
    words = line.split()
    if len(words) > 16 or line.rstrip().endswith((".", ";")) and not re.search(DATE_RANGE, line, re.I):
        return None
    if not re.search(r"[a-z]{3,}", re.sub(DATE_RANGE + "|" + MONTHS, " ", fold(line), flags=re.I)):
        return None  # a line that is only dates ("March 2024 - Present") is not another role
    segs = [s for s in re.split(SEGMENT, line.strip()) if s.strip()]
    if section == "header":
        return segs  # the top of a resume: name, headline title, contact; every segment may hold the headline title
    if len(segs) >= 2 or re.search(DATE_RANGE, line, re.I) or len(words) <= 6:
        return [segs[0]] if segs else None
    return None


def analyze(text, explain=True):
    """The whole pipeline on one resume. Returns the label(s), scores and, with explain, what each step saw."""
    stats, lines = {}, split_lines(text)
    section, role_i, steps_sections = "header", -1, []
    feats = {}   # phrase key -> weight
    fam_s = {f: 0.0 for f in FAMILIES}
    evidence = {f: {} for f in FAMILIES}
    all_toks = 0

    def add(k, hits, where):
        rec = RECENCY[min(max(role_i, 0), len(RECENCY) - 1)]
        for fam, kind in hits:
            if kind == "titles":
                ww = TITLE_W["mention"] if where == "mention" else TITLE_W[where] * rec
            else:
                ww = SECTION_W.get(section, 1.0) * rec
            if ww <= 0:
                continue
            fam_s[fam] += ww * SPEC[k]
            feats[k] = feats.get(k, 0) + ww
            evidence[fam][k] = evidence[fam].get(k, 0) + ww * SPEC[k]

    for li, line in enumerate(lines):
        if section == "header" and li >= HEADER_LINES:
            section = "body"  # no section headers: read the rest like an experience section
        sec = section_of(line)
        if sec:
            section = sec
            if sec not in steps_sections:
                steps_sections.append(sec)
            continue
        title_segs = role_title(line, section)
        toks = tokens(line, stats)
        all_toks += len(toks)
        if title_segs and section in ("experience", "body"):
            role_i += 1
        if title_segs:
            # the title segment(s) count as titles; the rest of the line (employer, place, dates) counts for nothing
            for seg in title_segs:
                for k, hits in match(tokens(seg)):
                    add(k, hits, "title")
            continue
        where = "summary" if section == "summary" else "mention"
        for k, hits in match(toks):
            add(k, hits, where)

    total = sum(fam_s.values())
    # nearest centroid: cosine between the resume's phrase vector and each family's centroid
    norm = math.sqrt(sum(v * v for v in feats.values())) or 1.0
    cos = {}
    for f, c in CENTROID.items():
        cn = math.sqrt(sum(v * v for v in c.values())) or 1.0
        cos[f] = sum(feats.get(k, 0) * v for k, v in c.items()) / (norm * cn)
    lex_share = {f: (s / total if total else 0.0) for f, s in fam_s.items()}
    cos_sum = sum(cos.values()) or 1.0
    final = {f: BLEND * lex_share[f] + (1 - BLEND) * cos[f] / cos_sum for f in FAMILIES}
    ranked = sorted(final.items(), key=lambda x: (-x[1], x[0]))
    if total < MIN_EVIDENCE:
        labels, conf = [], 0.0
    else:
        top = ranked[0][1]
        labels = [f for f, s in ranked if s >= top * SECONDARY and s >= 0.12][:3]
        conf = top
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    level = "none" if not labels else "high" if conf >= 0.5 and conf - second >= 0.25 else "medium" if conf >= 0.3 else "low"
    out = {"label": labels[0] if labels else "unclassified", "labels": labels, "confidence": round(conf, 3),
           "level": level, "hybrid": len(labels) > 1, "evidence_total": round(total, 2)}
    if explain:
        uniq = sorted(set(tokens(text)))
        out["steps"] = {
            "tokens": stats.get("raw", 0), "stopwords": stats.get("stopwords", 0), "aliases": stats.get("aliases", 0),
            "terms": all_toks, "vocabulary": len(uniq), "sample": uniq[:24], "lines": len(lines),
            "sections": steps_sections, "roles": max(role_i + 1, 0), "phrases": len(feats),
            "top_features": [k for k, _ in sorted(feats.items(), key=lambda x: -x[1])[:12]],
            "scores": [{"family": f, "p": round(s, 3), "evidence": [k for k, _ in sorted(evidence[f].items(), key=lambda x: -x[1])[:5]]}
                       for f, s in ranked[:6] if s > 0],
        }
    return out


# Back-off for posting titles that name no full role ("Director, Sales Development", "Senior GRC Engineer",
# "Manager, Strategic Finance"): the domain words in the title decide. Used only when no title phrase matched.
CUES = {
    "software": ["engineering", "software", "frontend", "backend", "full stack", "developer experience", "mobile", "web"],
    "ai / ml": ["ai", "machine learning", "ml", "llm", "research engineer", "applied ai", "model", "inference", "agent"],
    "data": ["data", "analytics", "analytical", "insights", "bi"],
    "devops / sre": ["infrastructure", "reliability", "devops", "cloud", "network", "systems administrator", "datacenter"],
    "security": ["security", "threat", "grc", "trust", "safety", "fraud", "detection", "privacy", "identity", "safeguard"],
    "hardware / embedded": ["hardware", "firmware", "embedded", "silicon", "electrical", "chip", "rf"],
    "product": ["product", "pm"],
    "design": ["design", "designer", "ux", "brand design", "creative"],
    "program / project": ["program", "project", "pmo", "delivery"],
    "solutions / sales engineering": ["solutions", "solution", "pre sales", "implementation", "deployment", "solutions consultant", "technical account"],
    "sales": ["sales", "account", "revenue", "business development", "gtm", "go to market", "commercial", "partnerships", "partner", "channel", "deal desk"],
    "marketing": ["marketing", "brand", "growth", "communications", "content", "community", "events", "pr", "demand", "advocate"],
    "customer success / support": ["customer", "support", "success", "client", "experience", "onboarding"],
    "finance / accounting": ["finance", "financial", "accounting", "tax", "treasury", "payroll", "revenue accounting", "fp a", "billing", "procurement finance"],
    "healthcare": ["clinical", "nurse", "medical", "health", "patient", "pharmacy"],
    "education": ["education", "teacher", "teaching", "learning", "curriculum", "academic"],
    "legal": ["legal", "counsel", "compliance", "regulatory", "policy", "law", "privacy counsel", "contracts"],
    "people / hr": ["people", "recruiting", "recruiter", "talent", "hr", "human resources", "workplace", "total rewards", "compensation"],
    "operations / supply chain": ["operations", "supply", "freight", "customs", "ocean", "real estate", "logistics", "procurement", "sourcing", "fulfillment", "strategy and operations", "bizops"],
    "administrative": ["assistant", "administrative", "office", "receptionist", "coordinator"],
    "research / science": ["research", "scientist", "science", "lab"],
    "engineering (non-software)": ["mechanical", "civil", "manufacturing", "process", "industrial", "quality"],
    "skilled trades": ["technician", "maintenance", "repair", "electrician", "installer"],
    "hospitality / retail": ["retail", "store", "restaurant", "hospitality", "guest"],
    "creative / media": ["writer", "editor", "video", "content writer", "editorial", "producer"],
}


def _cue_index():
    idx = {}
    for fam, words in CUES.items():
        for w in words:
            k = phrase_key(w)
            if k:
                idx.setdefault(k, set()).add(fam)
    return {k: sorted(v) for k, v in idx.items()}


CUE_INDEX = _cue_index()
CUE_N = max((len(k.split()) for k in CUE_INDEX), default=1)


def classify_title(title):
    """A posting title -> the families it belongs to (same tokens, same phrases; titles weigh 3, terms 1). Titles that
    name no full role fall back to their domain words (CUES), each split by how many families share it."""
    s = {}
    toks = tokens(title)
    found_title = False
    for k, hits in match(toks):
        for fam, kind in hits:
            s[fam] = s.get(fam, 0) + (TITLE_W["title"] if kind == "titles" else 1.0) * SPEC[k]
            found_title = found_title or kind == "titles"
    if not found_title:
        i, n = 0, len(toks)
        while i < n:  # longest-first over the cue words
            for size in range(min(CUE_N, n - i), 0, -1):
                k = " ".join(toks[i:i + size])
                if k in CUE_INDEX:
                    fams = CUE_INDEX[k]
                    for fam in fams:
                        s[fam] = s.get(fam, 0) + 1.0 / len(fams)
                    i += size
                    break
            else:
                i += 1
    if not s:
        return []
    top = max(s.values())
    return [f for f, v in sorted(s.items(), key=lambda x: (-x[1], x[0])) if v >= top * 0.5 and v >= 0.5]


def export():
    """The data the web port needs (scripts/try_rules.py writes it into apps/web/lib/try-rules.json)."""
    return {"families": FAMILIES, "stop": sorted(STOP), "keep": sorted(KEEP), "aliases": ALIASES, "sections": SECTIONS,
            "section_w": SECTION_W, "title_w": TITLE_W, "recency": RECENCY, "min_evidence": MIN_EVIDENCE,
            "secondary": SECONDARY, "blend": BLEND, "max_n": MAX_N, "header_lines": HEADER_LINES, "bullet": BULLET, "date_range": DATE_RANGE, "months": MONTHS,
            "segment": SEGMENT, "cues": CUES}
