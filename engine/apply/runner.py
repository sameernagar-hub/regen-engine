"""Apply stage: fast form filler for Ashby + Greenhouse (Playwright, headed).

Answers come from profile/presets.json (RULES) plus per-job extras. A required field the engine
can't answer is never guessed: the job goes to the human queue and is not submitted.
Greenhouse email security codes: the runner pauses and waits for workspace/code.txt.

python -m engine apply batches/b1.json          # fill + submit every job in the batch
python -m engine apply batches/b1.json --dry    # fill only, screenshot to workspace/proof/
batch: [{"name":..., "url":..., "resume":"out/x.pdf", "extra":{"label regex":"answer"}, "note":"optional"}]
"""
import json, re, sys, time, os, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

from engine.config import WORKSPACE, in_workspace, profile_file
from engine.feedback.events import record
from engine import safety
from engine.apply import drafts
from engine.apply.scheduler import Quantum, RoundRobin, poll

P = json.load(open(os.environ.get("REGEN_PRESETS") or profile_file("presets.json")))
# "Can you work here without sponsorship for the next 5 years / long term?" is not the same question as "are you
# authorized without sponsorship (today)?". OPT answers Yes today but No long-term. Derived, never a new fact:
# whoever will need sponsorship in the future can't work long-term without it.
if P.get("needs_sponsorship_now_or_future") in ("Yes", "No"):
    P.setdefault("authorized_without_sponsorship_long_term", "No" if P["needs_sponsorship_now_or_future"] == "Yes" else "Yes")


def preferred_language():
    """The first general-purpose language your Fact Bank skills name (derived from facts, never invented)."""
    try:
        from engine.tailoring.tailor import vocabulary
        v = vocabulary()
    except (SystemExit, Exception):
        return None
    return next((name for name in ("Python", "Java", "TypeScript", "JavaScript", "Go", "C++", "C#") if name.lower() in v), None)


PREFERRED_LANGUAGE = P.get("preferred_language") or preferred_language()
LONG_TERM = r"without .{0,40}sponsorship.{0,60}(next \d+|\d+ years|long.?term|future|foreseeable|indefinitely|duration)|(next \d+ years|long.?term|indefinitely).{0,60}without .{0,40}sponsorship"


def edu_dates(path=None):
    """Highest degree's dates from the Fact Bank ("Aug 2024 - May 2026") -> {start_month, start_year, end_month, end_year}.
    Greenhouse education blocks ask for these as "Start date month/year"; without a Fact Bank entry they go to the human queue."""
    path = path or os.environ.get("REGEN_FACT_BANK") or profile_file("fact_bank.json")
    try:
        span = json.load(open(path, encoding="utf-8"))["education"][0][1]
        a, b = (datetime.datetime.strptime(x.strip(), "%b %Y") for x in span.split(" - "))
    except (OSError, KeyError, IndexError, ValueError):
        return {}
    return {"start_month": a.strftime("%B"), "start_year": str(a.year), "end_month": b.strftime("%B"), "end_year": str(b.year)}


EDU = edu_dates()
BAY_AREA = r"san francisco|san jose|oakland|berkeley|palo alto|mountain view|sunnyvale|santa clara|cupertino|fremont|menlo park|redwood city|san mateo|hayward|milpitas"
# (label regex, answer). First match wins. Answers for yes/no/select are matched against option text.
RULES = [
    # arbitration is a per-company legal decision: only answered via a job's "extra" (user approval), never by default
    (r"arbitrat", None),
    # demographic / EEO questions are always declined, and checked before anything else can match their long labels
    (r"gender|\brace\b|racial|ethnic|hispanic|latin[oax]|veteran|disab|sexual orientation|transgender|lgbt|communities you|which communit|^i identify|pronoun|chronic condition|armed forces|military status", "__DECLINE__"),
    (r"preferred (first )?name", P["first_name"]),
    (r"^(full )?name|legal (full )?name|full (legal )?name", P["first_name"] + " " + P["last_name"]),
    (r"address line 1|street address|^address$|mailing address", P.get("address_line1")),  # None unless you add it to presets
    (r"first name", P["first_name"]), (r"last name", P["last_name"]),
    (r"e-?mail", P["email"]), (r"phone", P["phone"]),
    (r"hear about|how did you find|learned about|(first )?learn about .{0,40}(employer|us|company|role|position|job)|^source\b|(job|application|referral|candidate) source", "Company careers page"),  # before the link rules: these labels often list "LinkedIn"
    (r"linkedin", P["linkedin"]),
    (r"github|website|portfolio|other (web)?site|personal site|other url|additional (url|link)|^url$", P["github"]),
    (r"(preferred|favou?rite|strongest|primary) (programming |coding )?language", PREFERRED_LANGUAGE),
    # Legal / status answers come ONLY from your presets (never hardcoded). An unset preset -> human queue.
    # "authorized ... WITHOUT sponsorship" is a different question from "will you need sponsorship", so it has its own key.
    (LONG_TERM, P.get("authorized_without_sponsorship_long_term")),  # before the plain "without sponsorship" rule
    (r"without (the need for |requiring |needing )?(current or future )?(visa |employer |employment )?sponsorship", P.get("authorized_without_sponsorship")),
    (r"(will|do) you (now or in the future )?(require|need) (any )?(work |employment )?(authori[sz]ation|permit)", P.get("needs_sponsorship_now_or_future")),
    (r"(require|need).{0,60}(sponsor|visa|immigration)|sponsor|(file|submit) a petition|employment.based (visa|immigration)", P.get("needs_sponsorship_now_or_future")),
    (r"(currently|presently) (in|on|hold(ing)?) (an? )?f-?1( status| visa)?", P.get("f1_status")),
    (r"^(what is )?your country\W*$|^country of residence", P["country"]),
    (r"^(what is )?your state\b|state ?/ ?province", P["state"]),
    (r"authori[sz]ed to work|eligible to work|legally (authori|work|permitted)|work authori", P.get("work_authorized_us")),
    # "What company are you currently employed at?" must not reach the previous-employer rule below (it answered "No")
    (r"(what|which) (company|organi[sz]ation|employer) .{0,30}(employed|work(ing)?) (at|for)|(currently|presently) employed (at|by|with)\b.{0,10}\?|worked (at|for) most recently", P["current_employer"]),
    (r"(ever )?(been )?(previously )?employed (by|at)|worked (for|at) .{0,30} before|former employee|previous employee|(currently|previously|ever).{0,30}work(ed)? (at|for) (?!(a|an|any|or|with|the|one|another)\b)", P.get("previous_employer_of_company", "No")),
    (r"non-?compete|non-?solicit|subject to any agreement", P.get("non_compete")),
    (r"government|public official|family members", P.get("government_official_or_family")),
    (r"security clearance|active clearance", P.get("security_clearance")),
    (r"city,? (and|&|/) state|state (and|&|/) city", f"{P['city']}, {P['state']}"),  # before the state-only rule
    (r"(country|where).{0,40}(reside|based|located|live)|^country", P["country"]),
    (r"countr(y|ies) .{0,30}(anticipate|plan|expect|intend|would like) (to )?work", P["country"]),
    (r"(plan|intend|want|prefer) to work remotely|do you plan to work (from a )?remote", P.get("plans_to_work_remotely")),
    (r"(state|province).{0,30}(reside|live|located|working from|work from)", P["state"]),
    (r"city.{0,40}(reside|live|located)", P["city"]),
    # location boxes autocomplete worldwide: "San Jose" alone can resolve to San José, Costa Rica
    (r"current location|where are you located|^location", f"{P['city']}, {P['state']}"),
    (r"current (or previous )?(employer|company)|current \(or most recent\) company|most recent (employer|company)|^company", P["current_employer"]),
    (r"address (from which|where) you (plan|will|intend)|where (will|do) you (plan to )?work from|work(ing)? location address", f"{P['city']}, {P['state']}"),
    (r"located in the united states|reside in the (united states|us)|currently live in the us|based in the (u\.?s\.?|united states|us)\b|(live|reside|located) in the (u\.?s\.?|us)\b", P.get("lives_in_us")),
    (r"(ever )?worked for .{0,40}(company|previously|before)|interviewed (at|with) .{0,30} before", P.get("previous_employer_of_company")),
    (r"related to|close personal relationship|relatives? (who |that )?(currently )?work|(personal|familial|family).{0,3}(/familial )?relationships?|(relatives?|friends?|family members?)( or (relatives?|friends?|family))? .{0,30}(work|employ)", P.get("relatives_at_company")),
    (r"(willing|consent|agree) to (undergo |complete |a )*(a )?background (check|screen)", P.get("willing_background_check")),
    (r"(based|live|located|reside) (in|near) (or around )?the (san francisco )?bay area|in or around the (san francisco )?bay area",
     "Yes" if re.search(BAY_AREA, P.get("city", ""), re.I) else None),
    (r"current (or previous )?(job )?title", P["current_title"]),
    (r"zip|postal code", P["zip"]),
    (r"^city$", P["city"]), (r"^state$", P["state"]),
    (r"previously worked (at|for)|worked at .{0,30} (before|previously)", P.get("previous_employer_of_company")),
    (r"processing of personal data|personal data|ai policy|data privacy|privacy notice|candidate privacy|(authori[sz]e|consent).{0,80}(use|process|store|retain).{0,40}(information|data)", "__ACK__"),
    (r"relocation assistance|require relocation|need relocation", P.get("needs_relocation_assistance")),
    (r"accept the (listed )?salary|comfortable with the (salary|pay|compensation) range", P.get("accept_posted_salary_range")),
    (r"at least 18|18 years of age|over 18", P.get("over_18")),
    (r"(office|location)s? .{0,40}(would|do) you (prefer|like)|prefer.{0,40}(office|location)", P.get("preferred_location")),  # before the onsite yes/no rule
    (r"(office|in-person|onsite|on-site|hybrid|relocat|commut|remote-eligible states)", P.get("open_to_onsite_or_relocation")),
    (r"do you have an? (college|university|bachelor.?s?|undergraduate)? ?degree|completed an? (bachelor|college|university)", P.get("has_degree")),
    (r"currently enrolled|enrolled in (full.time )?(education|school|a degree)", P.get("currently_enrolled")),
    (r"university|school|college|institution", P["school"]),
    (r"discipline|field of study|\bmajor\b(?! life)", P.get("major")),
    (r"degree|highest (level of )?education", P["degree"]),
    (r"gpa", P["gpa"]),
    (r"graduat.{0,20}(year|date)|year.{0,20}graduat|expected graduation", P["grad_year"]),
    (r"whatsapp|text message|sms", P.get("sms_opt_in")),
    (r"years of (professional |relevant )?experience|how many years", P["years_experience"]),
    # education block dates (Greenhouse): must come before the availability "start date" rule below
    (r"^start date month\W*$", EDU.get("start_month")), (r"^start date year\W*$", EDU.get("start_year")),
    (r"^end date month\W*$", EDU.get("end_month")), (r"^end date year\W*$", EDU.get("end_year")),
    (r"how soon .{0,40}start|able to start", P.get("start_date")),
    (r"start date|when can you start|available to start|earliest.{0,30}start", P.get("start_date")),
    (r"preferred (office |work )?location|location preference|which (office|location)|^office location", P.get("preferred_location")),
    (r"(open|willing|able) to travel|travel (requirement|up to|\d+ ?%)", P.get("open_to_travel")),
    (r"(18|eighteen) ?\+? (years|or older)|(over|at least) (the age of )?18|18\+ years of age", P.get("over_18")),
    (r"time ?zone", P.get("timezone")),
    # AI dev tools: answered only from your own resume line (Fact Bank s_aitools), never embellished
    (r"(which|what) ai (coding |dev(elopment)? )?tools|ai tools do you use", P.get("ai_tools")),
    (r"(actively )?use ai tool(s|ing)|used ai tooling", P.get("uses_ai_tools")),
    (r"salary|compensation expectation|desired pay|expected (annual |base |total )?(compensation|pay)|compensation (range|requirements?)", P.get("salary_expectation")),
    (r"(current|former|previous) .{0,40}employee\?|employee of .{0,40}(current|former)", P.get("previous_employer_of_company", "No")),
    (r"referred by|were you referred|referral from|who referred you", P.get("referred", "No")),  # the engine applies cold
    # "Which of these have you used? Select all that apply" -> tick only the options your Fact Bank skills name
    (r"which of the following .{0,80}(used|worked with|experience|familiar|proficient)|select all .{0,40}(used|worked with|experience)", "__SKILLS__"),
    (r"privacy|consent|acknowledge|agree|certify|attest", "__ACK__"),
]
DECLINE = re.compile(r"decline|prefer not|don.t wish|do not wish|not to (answer|disclose|say)|choose not", re.I)
ACK = re.compile(r"^(yes|i agree|i acknowledge|i consent|i accept|i have read|i will read|i understand|i confirm|i certify|i attest|acknowledged?|agreed?|accepted?|confirm(ed)?|understood)\b", re.I)
NACK = re.compile(r"\b(do not|don.t|disagree|decline|not|no|reject)\b", re.I)

# Open-ended "why us" questions get the job's note (written per job from Fact Bank entries, reviewed before use).
NOTE_Q = re.compile(r"cover letter|why .{0,40}(interested|join|us|company|role|apply)|what (excites|interests|draws|attracts) you|why do you want|motivat\w* (you )?to (apply|join)|anything else|additional information", re.I)


def load_answer_bank():
    """profile/answers.json: answers you approved once, reused on every form.
    [{"pattern": "label regex", "answer": "...", "source": "where it comes from (fact ids / your approval date)"}]"""
    path = os.path.join(os.path.dirname(profile_file("presets.json")), "answers.json")
    if not os.path.exists(path):
        return []
    return [(a["pattern"], a["answer"]) for a in json.load(open(path, encoding="utf-8")) if a.get("answer") is not None]


BANK = load_answer_bank()


# Same fact, other spellings a dropdown may use (tried only when the main answer has no matching option).
ALIASES = {P["state"]: [P.get("state_abbr", "")], P["country"]: ["United States of America", "USA"],
           P["degree"]: ["Master of Science", "Masters", "M.S."],
           P["school"]: [P["school"].replace(", ", "-"), P["school"].replace(", ", " - "), P["school"].replace(",", "")]}
ALIASES = {k: [v for v in vs if v] for k, vs in ALIASES.items()}

MAX_OPTION = 80  # longest answer we will try to match against dropdown / choice options
YESNO_Q = re.compile(r"^\s*(are|do|does|did|will|would|have|has|had|is|was|can|could|should|may|any)\b", re.I)


def text_ok(label, ans):
    """A free-text box only gets a bare Yes/No when its label is actually a yes/no question
    (keeps "Yes" out of e.g. "What address will you work from? If you'd relocate, ...")."""
    sentences = re.split(r"(?<=[.?!])\s+", label or "")  # "This role is onsite Mon-Fri. Are you able to...?"
    return ans not in ("Yes", "No") or any(YESNO_Q.search(x) for x in sentences)


EXPERIENCE_Q = re.compile(r"^(do|have) you (have )?(any |professional |hands.on |industry |internship or industry |prior )*experience "
                          r"(with|in|using|developing|building|working (with|on)|on)\b(.{3,120}?)\??$", re.I)
CONCEPTS = {  # phrase in a question -> skill terms that count as having it (still must be in your Fact Bank)
    r"single.page|\bspa\b|front.?end|web app": ["react", "typescript", "javascript"],
    r"back.?end|server.side|\bapis?\b|web services": ["rest apis", "node.js", "spring boot", "fastapi", "microservices"],
    r"cloud|aws|amazon web services": ["aws"], r"\bml\b|machine learning|\bai\b|llm|gen.?ai": ["llms", "rag", "pytorch"],
    r"distributed|microservice": ["microservices", "kafka"], r"database|sql": ["postgresql", "sql", "mysql"],
}


def experience_answer(label):
    """"Do you have experience with X?" -> "Yes" when X (or what it means, see CONCEPTS) is in your Fact Bank
    skills, else None (never "No" by guess: an unknown goes to the human queue)."""
    m = EXPERIENCE_Q.search(" ".join(label.split()))
    if not m:
        return None
    from engine.tailoring.tailor import vocabulary, _hits
    vocab = vocabulary()
    phrase = m.group(6).lower()
    if _hits(phrase, vocab):
        return "Yes"
    for rx, terms in CONCEPTS.items():
        if re.search(rx, phrase) and any(t in vocab for t in terms):
            return "Yes"
    return None


def answer_for(label, extra):
    l = " ".join(label.split()).lower()
    # per-job extras first, then your approved answer bank, then the built-in rules
    for pat, ans in list(extra.items()) + BANK + RULES:
        if re.search(pat, l, re.I):
            if isinstance(ans, str) and ans.startswith("<"):
                return None  # an unfilled "<placeholder>" from profile.example is never submitted
            return ans  # None for rules that must come from the user (e.g. arbitration)
    return experience_answer(label)

_FB = None


def fact_bank():
    global _FB
    if _FB is None:
        try:
            _FB = json.load(open(os.environ.get("REGEN_FACT_BANK") or profile_file("fact_bank.json"), encoding="utf-8"))
        except (OSError, ValueError, SystemExit):
            _FB = {}
    return _FB


DRAFT = os.environ.get("REGEN_DRAFT", "1") != "0"  # draft open-ended answers from the Fact Bank instead of waiting


def answer(label, job):
    """Presets / approved answers / rules first, then the job's note for "why us", then a Fact Bank draft."""
    ans = answer_for(label, job.get("extra", {}))
    if NOTE_Q.search(label) and job.get("note"):
        return job["note"]
    if ans is None and DRAFT:
        d = drafts.draft(label, job, fact_bank(), WORKSPACE, P)
        if d:
            ans, fids = d
            job.setdefault("_drafted", []).append([" ".join(label.split())[:200], ans, fids])
            drafts.log_review(WORKSPACE, job, label, ans, fids)
    return ans

def _norm_opt(t):
    """Compare option text loosely: case, curly quotes, dashes and runs of whitespace don't matter."""
    t = (t or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return " ".join(t.split()).lower()


def skill_options(options):
    """Handles of the options whose text names a skill in your Fact Bank (whole-word match). O(options * T)."""
    from engine.tailoring.tailor import vocabulary, _hits
    vocab = vocabulary()
    return [h for t, h in options if _hits(t, vocab)]


def pick_option(options, ans):
    """options: list of (text, handle). Return best handle for answer."""
    if ans == "__SKILLS__":
        return None  # multi-select only: handled by skill_options
    if ans == "__DECLINE__":
        for t, h in options:
            if DECLINE.search(t): return h
        return None
    if ans == "__ACK__":
        for t, h in options:
            if ACK.search(t.strip()) and not NACK.search(t): return h
        return options[0][1] if len(options) == 1 and not NACK.search(options[0][0]) else None
    a = _norm_opt(ans)
    options = [(_norm_opt(t), h) for t, h in options]
    for t, h in options:
        if t == a: return h
    for t, h in options:
        if t.startswith(a): return h
    for t, h in options:
        if a in t: return h
    for t, h in options:  # short option inside a longer answer ("San Francisco" for "San Francisco Bay Area")
        o = t
        if len(o) >= 4 and re.search(r"(?<![a-z0-9])" + re.escape(o) + r"(?![a-z0-9])", a): return h
    if ans == P.get("preferred_location") and re.search(BAY_AREA, ans, re.I):
        # an office list ("San Mateo", "Raleigh", ...): any Bay Area office is the preferred location, else remote
        for rx in (BAY_AREA, r"\bremote\b"):
            for t, h in options:
                if re.search(rx, t, re.I): return h
    return None

# ---------------- Ashby ----------------
def fill_ashby(page, job, log):
    """Generator (see engine/apply/scheduler.py): yields at checkpoints and waits; returns the missing required labels."""
    url = job["url"].split("?")[0]
    if not url.endswith("/application"): url = url.rstrip("/") + "/application"
    page.goto(url); page.wait_for_selector("text=Submit Application", timeout=30000)
    fi = page.query_selector('input[name="_systemfield_resume"]')
    if not fi:
        for f in page.query_selector_all(".ashby-application-form-field-entry"):
            l = f.query_selector("label")
            if l and re.match(r"\s*resume", l.inner_text(), re.I) and f.query_selector("input[type=file]"):
                fi = f.query_selector("input[type=file]"); break
    if not fi: fi = page.query_selector_all("input[type=file]")[-1]
    fi.set_input_files(job["resume"])
    yield from poll(lambda: page.query_selector("text=Replace"), 20, 0.5)
    yield 6  # let Ashby's resume autofill finish before we answer anything (another job runs meanwhile)
    missing = []
    for _pass in range(2):
        missing = yield from ashby_fields(page, job, log, first=_pass == 0)
        yield 1  # answering can reveal follow-up questions; the second pass fills them
    return missing


ASHBY_REQUIRED = """e => { const l = e.querySelector('label, legend'); if (!l) return false;
  if (/required/i.test(l.className) || e.querySelector('[required],[aria-required=true]')) return true;
  return /\\*/.test(getComputedStyle(l, '::after').content || '') || /\\*/.test(getComputedStyle(l, '::before').content || ''); }"""


def ashby_fields(page, job, log, first=True):
    """One pass over the visible Ashby fields. Required = a '*' in the label text, a [required] input, a 'required'
    label class, or a '*' drawn by CSS (seen 10-07: one board's asterisks were CSS-only, so blanks went to submit)."""
    missing = []
    seen = {a[0] for a in job.get("_answers", [])}
    for f in page.query_selector_all(".ashby-application-form-field-entry"):
        lab_el = f.query_selector("label, legend")
        if not lab_el: continue
        label = lab_el.inner_text().strip()
        req = "*" in label or f.evaluate(ASHBY_REQUIRED)
        label = label.rstrip("*").strip()
        if re.search(r"^resume", label, re.I): continue
        if first or label[:200] not in seen:
            ans = answer(label, job)
        else:
            ans = next((a for l, a in job.get("_answers", []) if l == label[:200]), None)
        try:
            if first or label[:200] not in seen:  # log follow-up questions that appear on later passes too
                log(f"   . {label[:60]} -> {str(ans)[:30]}"); job.setdefault("_answers", []).append([label[:200], ans])
            ok = set_field(page, f, label, ans)
        except Exception as e:
            ok = False; log(f"  ! {label[:60]}: {e}")
        if not ok and req: missing.append(label[:90])
        yield  # checkpoint: the scheduler may switch jobs between fields
    return missing

def set_field(page, f, label, ans):
    if ans is None: return False
    txt = f.query_selector("input[type=text]:not([role=combobox]), input[type=email], input[type=tel], input[type=url], input[type=number], input:not([type]), textarea")
    combo = f.query_selector("input[role=combobox]")
    btns = [b for b in f.query_selector_all("button") if b.inner_text().strip() in ("Yes", "No")]
    choices = f.query_selector_all("input[type=radio], input[type=checkbox]")
    if len(ans) > MAX_OPTION and not txt:
        return False  # a drafted paragraph never goes into a button, choice or dropdown (it would be typed letter by letter)
    if txt and not ans.startswith("__") and ans not in ("Yes", "No"):
        txt.fill(""); txt.type(ans, delay=2); return True
    if btns:
        h = pick_option([(b.inner_text(), b) for b in btns], "Yes" if ans in ("__ACK__",) else ans)
        if not h: return False
        sel = lambda b: bool(re.search(r"active|selected", b.get_attribute("class") or "", re.I)) or b.get_attribute("aria-pressed") == "true"
        if not sel(h): h.click()
        return True
    if choices:
        opts = []
        for c in choices:
            lab = c.evaluate("e => (e.closest('label') || document.querySelector(`label[for='${e.id}']`) || e.parentElement).innerText")
            opts.append((lab, c))
        if ans == "__SKILLS__":
            hs = skill_options(opts)
            for h in hs:
                if not h.is_checked(): h.check(force=True)
            return bool(hs)
        h = pick_option(opts, ans)
        if h and h.is_checked(): return True
        if h:
            lab = h.evaluate_handle("e => e.closest('label') || document.querySelector(`label[for='${e.id}']`) || e.parentElement").as_element()
            lab.click()
            if not h.is_checked(): h.check(force=True)
            return h.is_checked()
        return False
    if combo:
        if ans.startswith("__"): return False
        cur = combo.input_value()
        if cur and (cur == ans or cur.lower().startswith(ans.lower())): return True
        combo.click(); combo.fill(""); combo.type(ans, delay=15); time.sleep(1.5)  # location boxes search remotely
        opts = page.query_selector_all("[role=option]")
        names = [o.inner_text().strip() for o in opts]
        h = pick_option(list(zip(names, opts)), ans)
        if h:
            want = names[opts.index(h)]
            h.click(); time.sleep(0.5)
            if combo.input_value() == want: return True
            combo.click(); combo.fill(""); combo.type(ans, delay=15); time.sleep(1.5)
            for _ in range(names.index(want) + 1): page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter"); time.sleep(0.5)
            if combo.input_value() == want: return True
        page.keyboard.press("Escape"); return False
    if txt:
        if ans.startswith("__") or not text_ok(label, ans): return False
        txt.fill(""); txt.type(ans, delay=2); return True
    return False

def submit_ashby(page):
    page.click("button:has-text('Submit Application')")
    for _ in range(25):
        yield 1
        body = page.inner_text("body")
        if re.search(r"successfully submitted|thank you for applying|application was submitted", body, re.I): return True, "success"
        m = re.findall(r"Missing entry for required field: [^\n]+", body)
        if m: return False, "; ".join(m)
        if re.search(r"flagged as possible spam", body, re.I):
            # bot detection: never worked around. You submit this one by hand (resume is ready).
            return False, "BOT-CHECK: Ashby flagged the automated submit; apply manually with the prepared resume"
    return False, "no confirmation seen (captcha?)"

# ---------------- Lever (jobs.lever.co/<co>/<id>/apply) ----------------
def lever_apply_url(url):
    u = url.split("?")[0].rstrip("/")
    return u if u.endswith("/apply") else u + "/apply"


def set_select(sel, ans):
    opts = [(o.inner_text().strip(), o) for o in sel.query_selector_all("option") if (o.get_attribute("value") or "").strip()]
    h = pick_option(opts, ans)
    if not h: return False
    sel.select_option(value=h.get_attribute("value")); return True


def fill_lever(page, job, log):
    page.goto(lever_apply_url(job["url"])); page.wait_for_selector("form", timeout=30000)
    yield 1.5
    missing = []
    page.set_input_files("input[name=resume], input#resume-upload-input, input[type=file]", job["resume"])
    for _ in range(20):  # Lever parses the resume and pre-fills name/email; wait for the upload to land
        yield 0.5
        if re.search(r"success|uploaded|" + re.escape(os.path.basename(job["resume"])[:20]), page.inner_text(".application-form, form")[:4000], re.I): break
    for f in page.query_selector_all("li.application-question, .application-question"):
        lab_el = f.query_selector(".application-label, .text, label")
        if not lab_el: continue
        raw = lab_el.inner_text().strip()
        req = "✱" in raw or "*" in raw or f.query_selector("[required]") is not None
        label = re.sub(r"[✱*]", "", raw).strip()
        if not label or re.match(r"(resume|cv)\b", label, re.I): continue
        ans = answer(label, job)
        if re.search(r"^current (company|employer)|^organization", label, re.I):
            ans = P.get("current_company") or ans
        log(f"   . {label[:60]} -> {str(ans)[:30]}"); job.setdefault("_answers", []).append([label[:200], ans])
        try:
            sel = f.query_selector("select")
            loc = f.query_selector("input[name=location], #location-input")
            if ans is None: ok = False
            elif sel: ok = set_select(sel, ans)
            elif loc:
                # type "City, State" and only take a suggestion in that state/US ("San Jose" alone picked Costa Rica)
                want = f"{P['city']}, {P['state']}"
                loc.fill(""); loc.type(want, delay=20); yield 2
                opts = page.query_selector_all(".dropdown-location, .dropdown-results div, [class*=dropdown] li")
                us = re.escape(P["state"]) + r"|\b" + re.escape(P.get("state_abbr") or "##") + r"\b|United States|\bUSA?\b"
                good = [o for o in opts if re.search(us, o.inner_text())]
                if good: good[0].click(); ok = True
                else:
                    loc.fill(want); page.keyboard.press("Escape"); ok = not opts
            elif f.query_selector("textarea") and not ans.startswith("__"):
                if not text_ok(label, ans) and not (NOTE_Q.search(label) and job.get("note")) and not drafts.is_open(label): ok = False
                else: f.query_selector("textarea").fill(ans); ok = True
            else:
                ok = set_field(page, f, label, ans)
        except Exception as e:
            ok = False; log(f"  ! {label[:60]}: {e}")
        if not ok and req: missing.append(label[:90])
        yield  # checkpoint
    # EEO block: always decline
    for sel in page.query_selector_all("select[name^='eeo']"):
        try: set_select(sel, "__DECLINE__") or None
        except Exception: pass
    return missing


def submit_lever(page):
    page.click("#btn-submit, button[type=submit]:has-text('Submit')")
    for _ in range(25):
        yield 1
        u = page.url; body = page.inner_text("body")
        if "/thanks" in u or re.search(r"application (has been )?submitted|thank you for (applying|your application)", body, re.I):
            return True, "success"
        cap = page.query_selector("iframe[src*=hcaptcha]:visible, iframe[src*=recaptcha]:visible, .h-captcha:visible")
        if cap and _ > 2:
            # never solved or worked around: the form stays filled for you to finish
            return False, "CAPTCHA: Lever asked for a human check; finish this one by hand (form filled, resume ready)"
        errs = page.query_selector_all(".error-message:visible, .application-error:visible")
        if errs and _ > 3: return False, "; ".join(e.inner_text()[:80] for e in errs[:5])
    return False, "no confirmation seen"

# ---------------- Workable (apply.workable.com/<co>/j/<id>/apply) ----------------
def workable_apply_url(url):
    u = url.split("?")[0].rstrip("/")
    return u if u.endswith("/apply") else u + "/apply"


def fill_workable(page, job, log):
    page.goto(workable_apply_url(job["url"]), wait_until="networkidle"); page.wait_for_selector("form", timeout=30000)
    yield 1.5
    for b in page.query_selector_all("button:has-text('Decline all')"):  # cookie banner: most private choice
        try: b.click(timeout=2000)
        except Exception: pass
    missing = []
    fi = page.query_selector("input[type=file][required]") or page.query_selector_all("input[type=file]")[-1]
    fi.set_input_files(job["resume"]); yield 4
    std = {"firstname": P["first_name"], "lastname": P["last_name"], "email": P["email"],
           "phone": P["phone"].replace("+1 ", "").replace("+1", ""),
           # Workable's own hint: "Include your city, region, and country" (no street address needed)
           "address": f"{P['city']}, {P['state']}, {P['country']}"}
    for name, val in std.items():
        el = page.query_selector(f"input[name={name}]")
        if el: el.fill(val)
    # free-text questions
    for el in page.query_selector_all("input[aria-labelledby]:not([type=radio]):not([type=checkbox]):not([type=file]), textarea[aria-labelledby]"):
        if el.get_attribute("name") in std: continue
        lab = page.query_selector("#" + el.get_attribute("aria-labelledby").split()[0])
        label = (lab.inner_text() if lab else "").strip().rstrip("*").strip()
        req = el.get_attribute("required") is not None or el.get_attribute("aria-required") == "true"
        ans = answer(label, job)
        log(f"   . {label[:60]} -> {str(ans)[:30]}"); job.setdefault("_answers", []).append([label[:200], ans])
        ok = bool(ans) and not ans.startswith("__") and text_ok(label, ans)
        if ok: el.fill(ans)
        if not ok and req: missing.append(label[:90])
        yield  # checkpoint
    # single / multiple choice
    for grp in page.query_selector_all("fieldset[role=radiogroup][aria-labelledby], fieldset[role=group][aria-labelledby]"):
        lab = page.query_selector("#" + grp.get_attribute("aria-labelledby").split()[0])
        label = (lab.inner_text() if lab else "").strip().rstrip("*").strip()
        req = grp.query_selector("[aria-required=true], [required]") is not None
        ans = answer_for(label, job.get("extra", {}))
        log(f"   . {label[:60]} -> {str(ans)[:30]}"); job.setdefault("_answers", []).append([label[:200], ans])
        opts = [(o.inner_text().strip(), o) for o in grp.query_selector_all("[role=radio], [role=checkbox]")]
        h = pick_option(opts, ans) if ans and opts else None
        if h:
            if h.get_attribute("aria-checked") != "true": h.click()
        elif req: missing.append(label[:90])
    return missing


def submit_workable(page):
    page.click("button[type=submit]:has-text('Submit')")
    for _ in range(25):
        yield 1
        body = page.inner_text("body")
        if re.search(r"thank(s| you) for (applying|your application)|application (has been |was )?(submitted|received)", body, re.I):
            return True, "success"
        cap = page.query_selector("iframe[src*=hcaptcha]:visible, iframe[src*=recaptcha]:visible, iframe[src*=challenges]:visible") \
            or re.search(r"verify you are human|i.m not a robot", body, re.I)
        if cap and _ > 1:  # Cloudflare Turnstile lives in a closed shadow root: its text is the reliable signal
            return False, "CAPTCHA: Workable asked for a human check (Cloudflare); apply by hand with the prepared resume"
        errs = page.query_selector_all("[role=alert]:visible, [data-ui$=error]:visible")
        if errs and _ > 3: return False, "; ".join(e.inner_text()[:80] for e in errs[:5])
    return False, "no confirmation seen"

# ---------------- Greenhouse (job-boards.greenhouse.io) ----------------
def gh_embed_url(url):
    """The bare embedded application form is faster and has a stable DOM across company skins."""
    m = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    return f"https://job-boards.greenhouse.io/embed/job_app?for={m.group(1)}&token={m.group(2)}" if m else url


def fill_gh(page, job, log):
    url = gh_embed_url(job["url"])
    page.goto(url); page.wait_for_selector("#application-form, form", timeout=30000)
    try: page.wait_for_load_state("networkidle", timeout=15000)
    except Exception: pass
    yield 1.5
    missing = []
    for attempt in range(3):
        page.set_input_files("input#resume" if page.query_selector("input#resume") else "input[type=file]", job["resume"]); yield 2.5
        if os.path.basename(job["resume"]) in page.inner_text("body"): break
        yield 2
    else:
        missing.append("RESUME UPLOAD FAILED")
    ph = page.query_selector("input#phone")
    if ph:
        ph.fill(P["phone"].replace("+1 ", ""))
        cc = page.query_selector("#country, .phone-input input[role=combobox], [id*=phone] input[role=combobox]")
        if cc:
            try:
                cc.click(timeout=3000); cc.type("United States", delay=10); yield 0.8
                # options read "United States+1"; Enter alone picked whatever was highlighted (seen: "Select a country")
                us = next((o for o in page.query_selector_all("[role=option]") if re.match(r"\s*United States\s*\+?\s*1\b", o.inner_text())), None)
                if us: us.click()
                else: page.keyboard.press("Enter")
            except Exception: pass
    seen = set()
    for f in page.query_selector_all(".field-wrapper, fieldset, .checkbox, [class*=demographic] .select, .eeoc__question, .education--form .select__container, .education--form .text-input-wrapper"):
        key = f.evaluate("e => e.innerText.slice(0,120)")
        if key in seen: continue
        seen.add(key)
        lab_el = f.query_selector("label, legend")
        if not lab_el: continue
        label = lab_el.inner_text().strip(); req = "*" in label
        label = label.rstrip("*").strip()
        if re.search(r"^resume", label, re.I) or (re.search(r"^cover letter", label, re.I) and not req and not job.get("note")): continue
        if f.query_selector("input#phone") or re.fullmatch(r"(country|phone)", label, re.I) and f.query_selector("input#phone, #country"): continue
        ans = answer(label, job)
        if NOTE_Q.search(label) and ans and not ans.startswith("__"):
            ta = f.query_selector("textarea"); bt = f.query_selector("button:has-text('Enter manually')")
            if bt: bt.click(); yield 0.3; ta = f.query_selector("textarea")
            if ta:
                ta.fill(ans); log(f"   . {label[:60]} -> {ans[:30]}"); job.setdefault("_answers", []).append([label[:200], ans]); continue
        try:
            log(f"   . {label[:60]} -> {str(ans)[:30]}"); job.setdefault("_answers", []).append([label[:200], ans])
            ok = set_gh(page, f, ans, label)
        except Exception as e:
            ok = False; log(f"  ! {label[:60]}: {e}")
        if not ok and req: missing.append(label[:90])
        yield  # checkpoint
    return missing

def set_gh(page, f, ans, label=""):
    if ans is None: return False
    sel = f.query_selector("input[role=combobox], .select__input input, [class*=select__control]")
    choices = f.query_selector_all("input[type=checkbox], input[type=radio]")
    txt = f.query_selector("input[type=text]:not([role=combobox]), input[type=email], input[type=tel], input[type=url], input[type=number], textarea")
    if len(ans) > MAX_OPTION and (sel or choices):
        return False  # see set_field: drafts are for free-text boxes only
    if sel:
        inp = f.query_selector("input[role=combobox]") or sel
        terms = {"__DECLINE__": ["decline", "prefer not", "don't wish", "not wish"], "__ACK__": ["yes", "i acknowledge", "acknowledge", "agree", "understand", "read"],
                 "Company careers page": ["Company Website", "Company website", "Careers", "Website", "Job Board", "Other"]}.get(ans, [ans, ans[:12]])
        def options():
            opts = page.query_selector_all("[role=option], .select__option")
            return [o for o in opts if not re.search(r"no options|loading", o.inner_text(), re.I)]

        # fast path: open the menu once and choose from the full list (most selects have < 15 options)
        inp.click(timeout=4000); time.sleep(0.5)
        real = options()
        if not real:  # click focused the box without opening the menu
            page.keyboard.press("ArrowDown"); time.sleep(0.4); real = options()
        h = None
        if real:
            labeled = [(o.inner_text(), o) for o in real]
            for term in (terms if ans == "Company careers page" else [ans] + ALIASES.get(ans, [])):
                h = pick_option(labeled, term)
                if h: break
        for term in ([] if h else terms):
            inp.click(timeout=4000); inp.fill(""); inp.type(term, delay=15); time.sleep(0.9)
            real = options()
            labeled = [(o.inner_text(), o) for o in real]
            h = pick_option(labeled, term) if ans == "Company careers page" else next(
                (x for x in (pick_option(labeled, v) for v in [ans] + ALIASES.get(ans, [])) if x), None)
            if not h and len(real) == 1 and term.lower() in real[0].inner_text().lower() and not ans.startswith("__"):
                h = real[0]  # the only option left contains what we searched for
            if h: break
            page.keyboard.press("Escape")
        if not h:
            page.keyboard.press("Escape"); return False
        try: h.click(force=True, timeout=3000)
        except Exception:
            for _ in range(real.index(h)): page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
        time.sleep(0.3); return True
    if choices:
        opts = [(c.evaluate("e => (e.closest('label') || document.querySelector(`label[for='${e.id}']`) || e.parentElement).innerText"), c) for c in choices]
        if ans == "__SKILLS__":
            hs = skill_options(opts)
            for h in hs: h.check(force=True)
            return bool(hs)
        h = pick_option(opts, ans)
        if h: h.check(force=True); return True
        return False
    if txt:
        if ans.startswith("__") or not text_ok(label, ans): return False
        if txt.input_value(): return True
        txt.fill(ans); return True
    return False

def code_slug(page_url):
    m = re.search(r"for=([^&]+)&token=(\d+)|greenhouse\.io/([^/]+)/jobs/(\d+)", page_url or "")
    return "_".join(x for x in (m.groups() if m else ()) if x) or re.sub(r"[^A-Za-z0-9]+", "_", page_url or "job")[-40:]


def enter_email_code(page, job=None, wait=300):
    """Greenhouse emails an 8-char security code. Several jobs can wait at once (round-robin), so each waits on
    its own file: codes/<board>_<id>.wait holds the company and form URL, the operator writes the code to
    codes/<board>_<id>.txt. The legacy single code.txt is still accepted when only one job is waiting."""
    os.makedirs("codes", exist_ok=True)
    slug = code_slug(page.url)
    waitf, codef = f"codes/{slug}.wait", f"codes/{slug}.txt"
    print(f"   ...waiting for email security code in workspace/{codef}", flush=True)
    for f in (codef,):
        if os.path.exists(f): os.remove(f)
    open(waitf, "w").write(((job or {}).get("name") or "") + "\n" + page.url)
    open("WAITING_FOR_CODE", "w").write(page.url)

    def got():
        if os.path.exists(codef):
            return open(codef).read().strip()
        if os.path.exists("code.txt") and len([w for w in os.listdir("codes") if w.endswith(".wait")]) == 1:
            c = open("code.txt").read().strip(); os.remove("code.txt"); return c
        return None
    code = yield from poll(got, wait, 1.0)
    for f in (waitf, codef):
        if os.path.exists(f): os.remove(f)
    if not [w for w in os.listdir("codes") if w.endswith(".wait")] and os.path.exists("WAITING_FOR_CODE"):
        os.remove("WAITING_FOR_CODE")
    if not code:
        return False
    boxes = page.query_selector_all("input[id^=security-input]")
    if len(boxes) >= len(code):
        for b, ch in zip(boxes, code): b.fill(ch)
    else:
        (page.query_selector("input[name*=security], input[autocomplete=one-time-code]") or boxes[0]).fill(code)
    yield 0.5
    page.click("button[type=submit]:has-text('Submit'), button:has-text('Submit application')")
    return True

def submit_gh(page, job=None):
    page.click("button[type=submit]:has-text('Submit'), button:has-text('Submit application')")
    for _ in range(30):
        yield 1
        body = page.inner_text("body"); u = page.url
        # code step first: its page also contains words like "confirm", which once produced a false SUBMITTED
        code_step = page.query_selector("input[id^=security-input]") or re.search(r"(security|verification) code (was|has been) sent|enter the 8-character code", body, re.I)
        form_gone = not page.query_selector("button[type=submit]:visible, button:has-text('Submit application'):visible")
        if not code_step and form_gone and (re.search(r"thank you for (applying|your application)|application (has been |was )?(received|submitted)|we.ve received your application", body, re.I)
                              or re.search(r"/confirmation\b", u)):
            return True, "success"
        if code_step:
            ok = yield from enter_email_code(page, job)
            if not ok: return False, "EMAIL CODE REQUIRED (timed out)"
            continue
        errs = page.query_selector_all(".helper-text--error, [id$=-error], .error")
        if errs and _ > 3: return False, "; ".join(field_error(e) for e in errs[:6])
    return False, "no confirmation seen (captcha?)"


FIELD_OF = """e => { const w = e.closest('.field-wrapper, fieldset, .select__container, .text-input-wrapper, .checkbox, li, div');
  const l = w && (w.querySelector('label, legend') || (w.parentElement && w.parentElement.querySelector('label, legend')));
  return l ? l.innerText.trim() : ''; }"""


def field_error(e):
    """'This field is required.' -> 'Degree: This field is required.' so a failure says which field it was."""
    msg = e.inner_text().strip()[:80]
    try:
        lab = " ".join((e.evaluate(FIELD_OF) or "").split()).rstrip("*").strip()[:60]
    except Exception:
        lab = ""
    return f"{lab}: {msg}" if lab and lab.lower() not in msg.lower() else msg

def main(argv=None):
    """apply <batch.json> [--dry] [--only regex]   --only limits the batch to jobs whose name matches"""
    argv = sys.argv[1:] if argv is None else argv
    with in_workspace():
        jobs = json.load(open(argv[0]))
        if "--only" in argv:
            pat = argv[argv.index("--only") + 1]
            jobs = [j for j in jobs if re.search(pat, j.get("name", ""), re.I)]
        run(jobs, dry="--dry" in argv)


def ashby_cooling(hours=24):
    """After Ashby flags an automated submit, stop auto-submitting Ashby for a day: repeated flagged attempts
    could hurt the candidate's standing. Forms are still filled; the human clicks submit."""
    try:
        t = datetime.datetime.fromisoformat(open("ashby_cooldown").read().strip())
    except (OSError, ValueError):
        return False
    return datetime.datetime.now() - t < datetime.timedelta(hours=hours)


def already_submitted():
    """URLs whose latest (non-dry) status is SUBMITTED; a later correction event overrides an earlier one."""
    from engine.feedback.events import read
    latest = {}
    for e in read("application"):
        if not e.get("dry") and e.get("url"):
            latest[e["url"]] = e.get("status")
    return {u for u, s in latest.items() if s == "SUBMITTED"}


def job_task(page, job, dry, results, log_base=print):
    """One application as a generator: fill, airbags, submit, record. The scheduler interleaves several."""
    name = job.get("name") or job["url"]
    tag = re.sub(r"\s+", " ", name.split(" - ")[0])[:16]
    log = lambda s: log_base(f"[{tag}] {s.strip()}", flush=True)
    log(f"== {name}")
    ash = "ashbyhq" in job["url"]; lev = "jobs.lever.co" in job["url"]; wk = "workable.com" in job["url"]
    shot = ""
    if not (ash or lev or wk) and "greenhouse" not in job["url"]:
        status = f"NEEDS YOU: no adapter for {job.get('ats') or 'this site'} yet; resume ready at {job.get('resume')}"
    elif ash and not dry and ashby_cooling():
        # the tab is reused right after, so a filled-but-unsubmitted form would be lost anyway: don't spend the time
        status = "NEEDS YOU: Ashby cooldown after a bot-check; not opened (re-run after the cooldown, resume ready)"
    else:
        try:
            missing = yield from (fill_ashby(page, job, log) if ash else fill_lever(page, job, log) if lev
                                  else fill_workable(page, job, log) if wk else fill_gh(page, job, log))
            stamp = datetime.datetime.now().strftime("%m%d-%H%M%S")
            shot = f"proof/{re.sub(r'[^A-Za-z0-9]+', '_', name)[:50]}_{stamp}.png"
            # airbags: anything sensitive, unexpected or over the limits stops this job before submit
            problems = (safety.check_labels([a[0] for a in job.get("_answers", [])])
                        + safety.check_page(page.inner_text("body"), page.url, job["url"])
                        + safety.check_answers(job.get("_answers"), P)
                        + ([] if dry else safety.check_rate(name.split(" - ")[0])))
            if problems:
                page.screenshot(path=shot, full_page=True)
                status = "FLAGGED: " + safety.flag("airbag", name, " | ".join(problems), job["url"])
            elif missing:
                page.screenshot(path=shot, full_page=True)
                status = "NEEDS YOU: " + " | ".join(missing)
            elif dry:
                page.screenshot(path=shot, full_page=True); status = "filled (dry run)"
            elif ash and ashby_cooling():
                page.screenshot(path=shot, full_page=True)
                status = "NEEDS YOU: Ashby cooldown after a bot-check; form is filled, submit it by hand (resume ready)"
            else:
                sub = (lambda: submit_ashby(page)) if ash else (lambda: submit_lever(page)) if lev else \
                      (lambda: submit_workable(page)) if wk else (lambda: submit_gh(page, job))
                ok, msg = yield from sub()
                if not ok and ash and msg.startswith("Missing entry"):
                    # fields that only appeared after earlier answers: fill them and submit once more
                    log("   . Ashby reported missing fields; one more pass, then resubmit")
                    again = yield from ashby_fields(page, job, log, first=False)
                    if not again:
                        ok, msg = yield from sub()
                    else:
                        msg = "NEEDS YOU: " + " | ".join(again)
                page.screenshot(path=shot, full_page=True)
                if not ok and msg.startswith("BOT-CHECK"):
                    open("ashby_cooldown", "w").write(datetime.datetime.now().isoformat())
                status = "SUBMITTED" if ok else (msg if msg.startswith("NEEDS YOU") else "FAILED: " + msg)
        except Exception as e:
            status, shot = f"ERROR: {e}"[:200], ""
    log(f"   -> {status}")
    record("application", job=name, url=job["url"], status=status.split(":")[0], detail=status, proof=shot, answers=job.get("_answers"),
           drafted=job.get("_drafted"), resume=job.get("resume"), dry=dry)
    if status == "SUBMITTED":
        m = re.search(r"(?:jobs/|token=|gh_jid=)(\d+)", job["url"])
        if m:
            with open("ids.txt", "a") as fh: fh.write("," + m.group(1))
    results.append({"name": name, "url": job["url"], "status": status, "proof": shot, "at": datetime.datetime.now().isoformat(timespec="seconds")})
    json.dump(results, open("results_last.json", "w"), indent=1)
    return status


def ats_key(url):
    return "ashby" if "ashbyhq" in url else "lever" if "lever.co" in url else "workable" if "workable.com" in url else "greenhouse"


def interleave(jobs):
    """Order jobs so consecutive ones are on different companies and ATSs (round-robin over companies):
    the per-company cap and Ashby's bot checks see spread-out traffic, and the tabs don't all wait on one site.
    O(n) with a dict of deques."""
    import collections
    by = collections.OrderedDict()
    for j in jobs:
        by.setdefault((j.get("name") or j["url"]).split(" - ")[0].lower(), collections.deque()).append(j)
    out = []
    while by:
        for k in list(by):
            out.append(by[k].popleft())
            if not by[k]:
                del by[k]
    return out


def run(jobs, dry=False, concurrency=None):
    """Apply to every job, `concurrency` tabs at a time, round-robin with an adaptive quantum per ATS
    (engine/apply/scheduler.py). REGEN_TABS sets the number of tabs (default 3; 1 = one job at a time)."""
    os.makedirs("proof", exist_ok=True)
    done = already_submitted()
    for j in [j for j in jobs if j["url"] in done]:
        print(f"== {j.get('name') or j['url']}\n   -> already SUBMITTED, skipping", flush=True)
    jobs = interleave([j for j in jobs if j["url"] not in done])
    if not jobs:
        return []
    if safety.stop_requested():
        print("STOP file present (workspace/STOP): not starting", flush=True); return []
    concurrency = concurrency or int(os.environ.get("REGEN_TABS", "3"))
    results = []
    t0 = time.monotonic()
    with sync_playwright() as pw:
        # background tabs must not be throttled: their timers drive the ATS's own autofill and validation
        ctx = pw.chromium.launch_persistent_context(os.environ.get("REGEN_PW_PROFILE", "pw-profile"), headless=False, viewport={"width": 1300, "height": 900},
                                                    args=["--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                                                          "--disable-backgrounding-occluded-windows"])
        pages = list(ctx.pages[:1]) or [ctx.new_page()]
        while len(pages) < min(concurrency, len(jobs)):
            pages.append(ctx.new_page())
        for pg in pages:
            pg.set_default_timeout(15000)  # any single action that can't complete fails fast instead of stalling the batch
            pg.set_default_navigation_timeout(45000)

        def factory(job):
            def make(page):
                if safety.stop_requested():
                    def stopped():
                        print("STOP file present (workspace/STOP): skipping " + (job.get("name") or job["url"]), flush=True)
                        return "STOPPED"
                        yield
                    return stopped()
                return job_task(page, job, dry, results)
            return make

        from engine.apply.scheduler import Task
        tasks = [Task(j.get("name") or j["url"], ats_key(j["url"]), factory(j)) for j in jobs]
        rr = RoundRobin(Quantum(os.path.join(WORKSPACE, "sched_stats.json")), concurrency=concurrency,
                        on_switch=lambda t: None)
        finished = rr.run(tasks, pages)
        ctx.close()
    wall = time.monotonic() - t0
    stats = [t.stats() for t in finished]
    active = sum(s["active_s"] for s in stats)
    record("schedule", jobs=len(stats), tabs=concurrency, wall_s=round(wall, 1), active_s=round(active, 1),
           switches=rr.switches, quantum={k: round(rr.q.get(k), 2) for k in rr.q.stats},
           per_job=stats, errors=[f"{t.name}: {t.error}" for t in finished if t.error])
    print(f"== {len(stats)} jobs in {wall:.0f}s wall ({active:.0f}s active across {concurrency} tabs, {rr.switches} switches); "
          f"throughput {len(stats) / max(wall, 1) * 3600:.0f} jobs/h", flush=True)
    with open("results_log.jsonl", "a") as fh:
        for r in results: fh.write(json.dumps(r) + "\n")
    return results

if __name__ == "__main__":
    main()
