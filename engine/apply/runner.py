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

from engine.config import in_workspace, profile_file
from engine.feedback.events import record
from engine import safety

P = json.load(open(os.environ.get("REGEN_PRESETS") or profile_file("presets.json")))
BAY_AREA = r"san francisco|san jose|oakland|berkeley|palo alto|mountain view|sunnyvale|santa clara|cupertino|fremont|menlo park|redwood city|san mateo|hayward|milpitas"
# (label regex, answer). First match wins. Answers for yes/no/select are matched against option text.
RULES = [
    # arbitration is a per-company legal decision: only answered via a job's "extra" (user approval), never by default
    (r"arbitrat", None),
    # demographic / EEO questions are always declined, and checked before anything else can match their long labels
    (r"gender|\brace\b|racial|ethnic|hispanic|latin[oax]|veteran|disab|sexual orientation|transgender|lgbt|communities you|which communit|^i identify|pronoun|chronic condition|armed forces", "__DECLINE__"),
    (r"preferred (first )?name", P["first_name"]),
    (r"^(full )?name|legal (full )?name|full (legal )?name", P["first_name"] + " " + P["last_name"]),
    (r"address line 1|street address|^address$|mailing address", P.get("address_line1")),  # None unless you add it to presets
    (r"first name", P["first_name"]), (r"last name", P["last_name"]),
    (r"e-?mail", P["email"]), (r"phone", P["phone"]),
    (r"linkedin", P["linkedin"]),
    (r"github|website|portfolio|other (web)?site|personal site", P["github"]),
    # Legal / status answers come ONLY from your presets (never hardcoded). An unset preset -> human queue.
    # "authorized ... WITHOUT sponsorship" is a different question from "will you need sponsorship", so it has its own key.
    (r"without (the need for |requiring |needing )?(current or future )?(visa |employer |employment )?sponsorship", P.get("authorized_without_sponsorship")),
    (r"(require|need).{0,60}(sponsor|visa|immigration)|sponsor", P.get("needs_sponsorship_now_or_future")),
    (r"authori[sz]ed to work|eligible to work|legally (authori|work|permitted)|work authori", P.get("work_authorized_us")),
    (r"(ever )?(been )?(previously )?employed (by|at)|worked (for|at) .{0,30} before|former employee|previous employee|(currently|previously|ever).{0,30}work(ed)? (at|for) (?!(a|an|any|or|with|the|one|another)\b)", P.get("previous_employer_of_company", "No")),
    (r"non-?compete|non-?solicit|subject to any agreement", P.get("non_compete")),
    (r"government|public official|family members", P.get("government_official_or_family")),
    (r"security clearance|active clearance", P.get("security_clearance")),
    (r"(country|where).{0,40}(reside|based|located|live)|^country", P["country"]),
    (r"(state|province).{0,30}(reside|live|located|working from|work from)", P["state"]),
    (r"city.{0,40}(reside|live|located)|current location|where are you located|^location", P["city"]),
    (r"current (or previous )?(employer|company)|current \(or most recent\) company|most recent (employer|company)|^company", P["current_employer"]),
    (r"address (from which|where) you (plan|will|intend)|where (will|do) you (plan to )?work from|work(ing)? location address", f"{P['city']}, {P['state']}"),
    (r"located in the united states|reside in the (united states|us)|currently live in the us|based in the (u\.?s\.?|united states|us)\b|(live|reside|located) in the (u\.?s\.?|us)\b", P.get("lives_in_us")),
    (r"(ever )?worked for .{0,40}(company|previously|before)|interviewed (at|with) .{0,30} before", P.get("previous_employer_of_company")),
    (r"related to|close personal relationship|relatives? (who |that )?(currently )?work", P.get("relatives_at_company")),
    (r"(based|live|located|reside) (in|near) (or around )?the (san francisco )?bay area|in or around the (san francisco )?bay area",
     "Yes" if re.search(BAY_AREA, P.get("city", ""), re.I) else None),
    (r"current (or previous )?(job )?title", P["current_title"]),
    (r"hear about|how did you find|learned about|^source\b|(job|application|referral|candidate) source", "Company careers page"),
    (r"zip|postal code", P["zip"]),
    (r"^city$", P["city"]), (r"^state$", P["state"]),
    (r"previously worked (at|for)|worked at .{0,30} (before|previously)", P.get("previous_employer_of_company")),
    (r"processing of personal data|personal data|ai policy|data privacy|privacy notice|candidate privacy|(authori[sz]e|consent).{0,80}(use|process|store|retain).{0,40}(information|data)", "__ACK__"),
    (r"relocation assistance|require relocation|need relocation", P.get("needs_relocation_assistance")),
    (r"accept the (listed )?salary|comfortable with the (salary|pay|compensation) range", P.get("accept_posted_salary_range")),
    (r"at least 18|18 years of age|over 18", P.get("over_18")),
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
    (r"start date|when can you start|available to start|earliest.{0,30}start", P.get("start_date")),
    (r"preferred (office |work )?location|location preference|which (office|location)", P.get("preferred_location")),
    (r"salary|compensation expectation|desired pay", P.get("salary_expectation")),
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

YESNO_Q = re.compile(r"^\s*(are|do|does|did|will|would|have|has|had|is|was|can|could|should|may|any)\b", re.I)


def text_ok(label, ans):
    """A free-text box only gets a bare Yes/No when its label is actually a yes/no question
    (keeps "Yes" out of e.g. "What address will you work from? If you'd relocate, ...")."""
    return ans not in ("Yes", "No") or bool(YESNO_Q.search(label or ""))


def answer_for(label, extra):
    l = " ".join(label.split()).lower()
    # per-job extras first, then your approved answer bank, then the built-in rules
    for pat, ans in list(extra.items()) + BANK + RULES:
        if re.search(pat, l, re.I):
            if isinstance(ans, str) and ans.startswith("<"):
                return None  # an unfilled "<placeholder>" from profile.example is never submitted
            return ans  # None for rules that must come from the user (e.g. arbitration)
    return None

def _norm_opt(t):
    """Compare option text loosely: case, curly quotes, dashes and runs of whitespace don't matter."""
    t = (t or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return " ".join(t.split()).lower()


def pick_option(options, ans):
    """options: list of (text, handle). Return best handle for answer."""
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
    return None

# ---------------- Ashby ----------------
def fill_ashby(page, job, log):
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
    try: page.wait_for_selector("text=Replace", timeout=20000)
    except Exception: pass
    time.sleep(6)  # let Ashby's resume autofill finish before we answer anything
    missing = []
    for _pass in range(2):
      missing = []
      for f in page.query_selector_all(".ashby-application-form-field-entry"):
        lab_el = f.query_selector("label, legend")
        if not lab_el: continue
        label = lab_el.inner_text().strip(); req = "*" in label or f.query_selector("[required]") is not None
        label = label.rstrip("*").strip()
        if re.search(r"^resume", label, re.I): continue
        ans = answer_for(label, job.get("extra", {}))
        if NOTE_Q.search(label) and job.get("note"):
            ans = job["note"]
        try:
            if _pass == 0: log(f"   . {label[:60]} -> {str(ans)[:30]}"); job.setdefault("_answers", []).append([label[:200], ans])
            ok = set_field(page, f, label, ans)
        except Exception as e:
            ok = False; log(f"  ! {label[:60]}: {e}")
        if not ok and req: missing.append(label[:90])
      time.sleep(1)
    return missing

def set_field(page, f, label, ans):
    if ans is None: return False
    txt = f.query_selector("input[type=text]:not([role=combobox]), input[type=email], input[type=tel], input[type=url], input[type=number], input:not([type]), textarea")
    combo = f.query_selector("input[role=combobox]")
    btns = [b for b in f.query_selector_all("button") if b.inner_text().strip() in ("Yes", "No")]
    choices = f.query_selector_all("input[type=radio], input[type=checkbox]")
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
        time.sleep(1)
        body = page.inner_text("body")
        if re.search(r"successfully submitted|thank you for applying|application was submitted", body, re.I): return True, "success"
        m = re.findall(r"Missing entry for required field: [^\n]+", body)
        if m: return False, "; ".join(m)
        if re.search(r"flagged as possible spam", body, re.I):
            # bot detection: never worked around. You submit this one by hand (resume is ready).
            return False, "BOT-CHECK: Ashby flagged the automated submit; apply manually with the prepared resume"
    return False, "no confirmation seen (captcha?)"

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
    time.sleep(1.5)
    missing = []
    for attempt in range(3):
        page.set_input_files("input#resume" if page.query_selector("input#resume") else "input[type=file]", job["resume"]); time.sleep(2.5)
        if os.path.basename(job["resume"]) in page.inner_text("body"): break
        time.sleep(2)
    else:
        missing.append("RESUME UPLOAD FAILED")
    ph = page.query_selector("input#phone")
    if ph:
        ph.fill(P["phone"].replace("+1 ", ""))
        cc = page.query_selector("#country, .phone-input input[role=combobox], [id*=phone] input[role=combobox]")
        if cc:
            try:
                cc.click(timeout=3000); cc.type("United States", delay=10); time.sleep(0.8); page.keyboard.press("Enter")
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
        if re.search(r"^(resume|cover letter)", label, re.I) and not job.get("note"): continue
        if f.query_selector("input#phone") or re.fullmatch(r"(country|phone)", label, re.I) and f.query_selector("input#phone, #country"): continue
        ans = answer_for(label, job.get("extra", {}))
        if NOTE_Q.search(label) and job.get("note"):
            ta = f.query_selector("textarea"); bt = f.query_selector("button:has-text('Enter manually')")
            if bt: bt.click(); time.sleep(0.3); ta = f.query_selector("textarea")
            if ta: ta.fill(job["note"]); continue
        try:
            log(f"   . {label[:60]} -> {str(ans)[:30]}"); job.setdefault("_answers", []).append([label[:200], ans])
            ok = set_gh(page, f, ans, label)
        except Exception as e:
            ok = False; log(f"  ! {label[:60]}: {e}")
        if not ok and req: missing.append(label[:90])
    return missing

def set_gh(page, f, ans, label=""):
    if ans is None: return False
    sel = f.query_selector("input[role=combobox], .select__input input, [class*=select__control]")
    choices = f.query_selector_all("input[type=checkbox], input[type=radio]")
    txt = f.query_selector("input[type=text]:not([role=combobox]), input[type=email], input[type=tel], input[type=url], input[type=number], textarea")
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
        h = pick_option(opts, ans)
        if h: h.check(force=True); return True
        return False
    if txt:
        if ans.startswith("__") or not text_ok(label, ans): return False
        if txt.input_value(): return True
        txt.fill(ans); return True
    return False

def enter_email_code(page, wait=300):
    """Greenhouse emails an 8-char security code. Wait for it to be dropped into code.txt
    (by the Gmail reader), type it, and resubmit."""
    print("   ...waiting for email security code in code.txt", flush=True)
    if os.path.exists("code.txt"): os.remove("code.txt")
    open("WAITING_FOR_CODE", "w").write(page.url)
    for _ in range(wait):
        time.sleep(1)
        if os.path.exists("code.txt"):
            code = open("code.txt").read().strip(); os.remove("code.txt"); os.remove("WAITING_FOR_CODE")
            boxes = page.query_selector_all("input[id^=security-input]")
            if len(boxes) >= len(code):
                for b, ch in zip(boxes, code): b.fill(ch)
            else:
                (page.query_selector("input[name*=security], input[autocomplete=one-time-code]") or boxes[0]).fill(code)
            time.sleep(0.5)
            page.click("button[type=submit]:has-text('Submit'), button:has-text('Submit application')")
            return True
    os.remove("WAITING_FOR_CODE"); return False

def submit_gh(page):
    page.click("button[type=submit]:has-text('Submit'), button:has-text('Submit application')")
    for _ in range(30):
        time.sleep(1)
        body = page.inner_text("body"); u = page.url
        # code step first: its page also contains words like "confirm", which once produced a false SUBMITTED
        code_step = page.query_selector("input[id^=security-input]") or re.search(r"(security|verification) code (was|has been) sent|enter the 8-character code", body, re.I)
        form_gone = not page.query_selector("button[type=submit]:visible, button:has-text('Submit application'):visible")
        if not code_step and form_gone and (re.search(r"thank you for (applying|your application)|application (has been |was )?(received|submitted)|we.ve received your application", body, re.I)
                              or re.search(r"/confirmation\b", u)):
            return True, "success"
        if code_step:
            ok = enter_email_code(page)
            if not ok: return False, "EMAIL CODE REQUIRED (timed out)"
            continue
        errs = page.query_selector_all(".helper-text--error, [id$=-error], .error")
        if errs and _ > 3: return False, "; ".join(e.inner_text()[:80] for e in errs[:5])
    return False, "no confirmation seen (captcha?)"

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


def run(jobs, dry=False):
    os.makedirs("proof", exist_ok=True)
    done = already_submitted()
    skip = [j for j in jobs if j["url"] in done]
    for j in skip:
        print(f"== {j.get('name') or j['url']}\n   -> already SUBMITTED, skipping", flush=True)
    jobs = [j for j in jobs if j["url"] not in done]
    if not jobs:
        return
    results = []
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context("pw-profile", headless=False, viewport={"width": 1300, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(15000)  # any single action that can't complete fails fast instead of stalling the batch
        page.set_default_navigation_timeout(45000)
        for job in jobs:
            name = job.get("name") or job["url"]
            log = lambda s: print(s, flush=True)
            if safety.stop_requested():
                log("STOP file present (workspace/STOP): halting before " + name); break
            log(f"== {name}")
            ash = "ashbyhq" in job["url"]
            if not ash and "greenhouse" not in job["url"]:
                status = f"NEEDS YOU: no adapter for {job.get('ats') or 'this site'} yet; resume ready at {job.get('resume')}"
                log(f"   -> {status}")
                record("application", job=name, url=job["url"], status="NEEDS YOU", detail=status, proof="", resume=job.get("resume"), dry=dry)
                results.append({"name": name, "url": job["url"], "status": status, "proof": "", "at": datetime.datetime.now().isoformat(timespec="seconds")})
                continue
            try:
                missing = fill_ashby(page, job, log) if ash else fill_gh(page, job, log)
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
                    ok, msg = submit_ashby(page) if ash else submit_gh(page)
                    page.screenshot(path=shot, full_page=True)
                    if not ok and msg.startswith("BOT-CHECK"):
                        open("ashby_cooldown", "w").write(datetime.datetime.now().isoformat())
                    status = ("SUBMITTED" if ok else "FAILED: ") + ("" if ok else msg)
            except Exception as e:
                status, shot = f"ERROR: {e}"[:200], ""
            log(f"   -> {status}")
            record("application", job=name, url=job["url"], status=status.split(":")[0], detail=status, proof=shot, answers=job.get("_answers"),
                   resume=job.get("resume"), dry=dry)
            if status == "SUBMITTED":
                m = re.search(r"(?:jobs/|token=|gh_jid=)(\d+)", job["url"])
                if m:
                    with open("ids.txt", "a") as fh: fh.write("," + m.group(1))
            results.append({"name": name, "url": job["url"], "status": status, "proof": shot, "at": datetime.datetime.now().isoformat(timespec="seconds")})
            json.dump(results, open("results_last.json", "w"), indent=1)
        ctx.close()
    with open("results_log.jsonl", "a") as fh:
        for r in results: fh.write(json.dumps(r) + "\n")

if __name__ == "__main__":
    main()
