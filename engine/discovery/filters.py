"""Domain filter shared by every discovery source: title, level, location, ineligible employers, dedupe.

Rules come from profile/domains.json (regex strings) layered over DEFAULT_DOMAIN. Optional keys:
  exclude_companies   regex of employers you can't or won't apply to (e.g. ITAR-restricted employers if they don't fit your eligibility)
  require_us          true (default) keeps only jobs located in the US or US-remote
"""
import json, os, re

from engine.config import PROFILE

DEFAULT_DOMAIN = {
    "include_titles": r"software|full.?stack|backend|back-end|ai engineer|machine learning engineer|ml engineer|forward.?deployed|platform engineer|product engineer|applied ai|founding engineer|member of technical staff|developer|\bsde\b|\bswe\b|data engineer",
    "exclude_titles": r"senior|\bsr\b|\bsr\.|staff|principal|\blead\b|manager|director|head of|\bvp\b|vice president|chief|architect|intern\b|internship|co-?op\b|apprentice|firmware|embedded|hardware|silicon|asic|fpga|verification|clearance|polygraph|top secret|\bts/sci\b|\biii\b|\biv\b|\b[345]\b|\bios\b|android|mobile|salesforce admin|technician|quality engineer|test engineer|sdet|2027|phd|research scientist|professor|instructor|recruiter|sales engineer|solutions? consultant",
    "exclude_companies": r"anduril|spacex|chaos industries|lockheed|raytheon|\brtx\b|northrop|general dynamics|bae systems|l3harris|leidos|\bsaic\b|booz allen|palantir|shield ai|epirus|saronic|hadrian|castelion|militar|defense",
    "require_us": True,
}
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
US_WORDS = re.compile(r"united states|\bUSA?\b|\bU\.S\.|americas?\b|north america|san francisco|new york|nyc|seattle|austin|boston|los angeles|palo alto|mountain view|san jose|sunnyvale|bay area|chicago|denver|atlanta|miami|washington|san diego|menlo park|redwood city|santa clara|cupertino|oakland|brooklyn|philadelphia|pittsburgh|portland|salt lake|raleigh|durham|nashville|dallas|houston|phoenix|detroit|minneapolis|columbus|irvine|santa monica|boulder|cambridge, ma|california|texas|massachusetts|illinois|colorado|virginia|georgia|florida|oregon|arizona|north carolina|pennsylvania|ohio|michigan|minnesota|utah|maryland|new jersey|tennessee", re.I)
NON_US = re.compile(r"\bUK\b|united kingdom|england|london|canada|toronto|vancouver|montreal|ontario|india|bangalore|bengaluru|hyderabad|pune|gurgaon|gurugram|noida|chennai|mumbai|dublin|ireland|germany|berlin|munich|paris|france|singapore|tokyo|japan|sydney|australia|amsterdam|netherlands|poland|warsaw|krakow|mexico|brazil|são paulo|sao paulo|israel|tel aviv|portugal|lisbon|spain|madrid|barcelona|italy|milan|romania|ukraine|serbia|argentina|colombia|chile|philippines|vietnam|korea|seoul|china|beijing|shanghai|hong kong|taiwan|emea|apac|latam|europe|switzerland|zurich|sweden|stockholm|denmark|copenhagen|norway|finland|belgium|austria|vienna|czech|prague|estonia|lithuania|greece|turkey|istanbul|egypt|nigeria|kenya|south africa|dubai|uae|saudi|new zealand|costa rica|pakistan|bangladesh|indonesia|malaysia|thailand", re.I)


def load_domain():
    d = dict(DEFAULT_DOMAIN)
    path = os.path.join(PROFILE, "domains.json")
    if os.path.exists(path):
        d.update(json.load(open(path, encoding="utf-8")))
    out = {k: (re.compile(v, re.I) if isinstance(v, str) else v) for k, v in d.items() if not k.startswith("_")}
    return out


def us_location(loc):
    """True when the location is in the US (or US-remote / unspecified remote). Empty location -> True (check later)."""
    loc = (loc or "").strip()
    if not loc:
        return True
    if US_WORDS.search(loc):
        return True
    if any(m in US_STATES for m in re.findall(r"(?:,|\s-)\s*([A-Z]{2})\b", loc)):
        return True
    if NON_US.search(loc):
        return False
    return bool(re.search(r"remote|anywhere|distributed", loc, re.I))


def keep(dom, title, location, company=""):
    """Return None if the job passes the domain filter, else a short reason it was dropped."""
    if not dom["include_titles"].search(title):
        return "title"
    if dom["exclude_titles"].search(title):
        return "level/title excluded"
    if company and dom.get("exclude_companies") and dom["exclude_companies"].search(company):
        return "company excluded"
    if dom.get("include_locations") and location and not dom["include_locations"].search(location) and not us_location(location):
        return "location"
    if dom.get("require_us", True) and not us_location(location):
        return "non-US"
    return None


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def applied_keys():
    """Everything already applied to (or deliberately skipped): job ids from ids.txt and company|title keys from the
    event log, so the same role found through two sources is never applied to twice."""
    from engine.config import WORKSPACE
    ids, keys = set(), set()
    p = os.path.join(WORKSPACE, "ids.txt")
    if os.path.exists(p):
        ids = {x.strip() for x in open(p).read().replace("\n", ",").split(",") if x.strip()}
    p = os.path.join(WORKSPACE, "events.jsonl")
    if os.path.exists(p):
        latest = {}  # job -> its latest event, so a correction overrides an earlier status
        for line in open(p, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("kind") == "application" and not e.get("dry"):
                latest[norm(e.get("job", ""))] = e
        for k, e in latest.items():
            if e.get("status") in ("SUBMITTED", "SKIPPED"):
                keys.add(k)
                m = re.search(r"(?:jobs/|token=|gh_jid=|ashbyhq\.com/[^/]+/|lever\.co/[^/]+/)([0-9a-f-]{6,})", e.get("url", ""))
                if m:
                    ids.add(m.group(1))
    return ids, keys
