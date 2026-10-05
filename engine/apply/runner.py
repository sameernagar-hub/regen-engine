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

P = json.load(open(os.environ.get("REGEN_PRESETS") or profile_file("presets.json")))
# (label regex, answer). First match wins. Answers for yes/no/select are matched against option text.
RULES = [
    (r"preferred (first )?name", P["first_name"]),
    (r"^(full )?name|legal name", P["first_name"] + " " + P["last_name"]),
    (r"first name", P["first_name"]), (r"last name", P["last_name"]),
    (r"e-?mail", P["email"]), (r"phone", P["phone"]),
    (r"linkedin", P["linkedin"]),
    (r"github|website|portfolio|other (web)?site|personal site", P["github"]),
    (r"(require|need).{0,60}(sponsor|visa|immigration)|sponsor", "Yes"),
    (r"authori[sz]ed to work|eligible to work|legally (authori|work|permitted)|work authori", "Yes"),
    (r"(ever )?(been )?(previously )?employed (by|at)|worked (for|at) .{0,30} before|former employee|previous employee", "No"),
    (r"non-?compete|non-?solicit|subject to any agreement", "No"),
    (r"government|public official|family members", "No"),
    (r"security clearance|active clearance", "No"),
    (r"(country|where).{0,40}(reside|based|located|live)|^country", P["country"]),
    (r"(state|province).{0,30}(reside|live|located|working from|work from)", P["state"]),
    (r"city.{0,40}(reside|live|located)|current location|where are you located|^location", P["city"]),
    (r"current (or previous )?(employer|company)|current \(or most recent\) company|most recent (employer|company)|^company", P["current_employer"]),
    (r"located in the united states|reside in the (united states|us)|currently live in the us", "Yes"),
    (r"(ever )?worked for .{0,40}(company|previously|before)|interviewed (at|with) .{0,30} before", "No"),
    (r"related to|close personal relationship|relatives? (who )?work", "No"),
    (r"current (or previous )?(job )?title", P["current_title"]),
    (r"hear about|how did you find|learned about|source", "Company careers page"),
    (r"zip|postal code", P["zip"]),
    (r"^city$", P["city"]), (r"^state$", P["state"]),
    (r"previously worked (at|for)|worked at .{0,30} (before|previously)", "No"),
    (r"processing of personal data|personal data|ai policy|data privacy|privacy notice|candidate privacy", "__ACK__"),
    (r"relocation assistance|require relocation|need relocation", "No"),
    (r"accept the (listed )?salary|comfortable with the (salary|pay|compensation) range", "Yes"),
    (r"at least 18|18 years of age|over 18", "Yes"),
    (r"(office|in-person|onsite|on-site|hybrid|relocat|commut|remote-eligible states)", "Yes"),
    (r"university|school|college|institution", P["school"]),
    (r"discipline|field of study|major", "Computer Science"),
    (r"degree", P["degree"]),
    (r"gpa", P["gpa"]),
    (r"graduat.{0,20}(year|date)|year.{0,20}graduat|expected graduation", P["grad_year"]),
    (r"whatsapp|text message|sms", "No"),
    (r"years of (professional |relevant )?experience|how many years", P["years_experience"]),
    (r"start date|when can you start|available to start", "Immediately (2 weeks notice)"),
    (r"salary|compensation expectation|desired pay", "Open to discussing; aligned with the posted range"),
    (r"gender|race|ethnic|hispanic|veteran|disab|sexual orientation|transgender|communit|^i identify|pronoun", "__DECLINE__"),
    (r"privacy|consent|acknowledge|agree|certify|attest", "__ACK__"),
]
DECLINE = re.compile(r"decline|prefer not|don.t wish|do not wish|not to (answer|disclose|say)|choose not", re.I)
ACK = re.compile(r"^(yes|i agree|i acknowledge|i consent|acknowledge|agree)", re.I)

def answer_for(label, extra):
    l = " ".join(label.split()).lower()
    for pat, ans in list(extra.items()) + RULES:
        if re.search(pat, l, re.I):
            return ans
    return None

def pick_option(options, ans):
    """options: list of (text, handle). Return best handle for answer."""
    if ans == "__DECLINE__":
        for t, h in options:
            if DECLINE.search(t): return h
        return None
    if ans == "__ACK__":
        for t, h in options:
            if ACK.search(t.strip()): return h
        return options[0][1] if len(options) == 1 else None
    a = ans.lower()
    for t, h in options:
        if t.strip().lower() == a: return h
    for t, h in options:
        if t.strip().lower().startswith(a): return h
    for t, h in options:
        if a in t.lower(): return h
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
        if re.search(r"additional information|anything else|cover letter|why .*(interested|join|us)", label, re.I) and job.get("note"):
            ans = job["note"]
        try:
            ok = set_field(page, f, label, ans)
        except Exception as e:
            ok = False; log(f"  ! {label[:60]}: {e}")
        if not ok and req: missing.append(label[:90])
      time.sleep(1)
    return missing

def set_field(page, f, label, ans):
    if ans is None: return False
    txt = f.query_selector("input[type=text]:not([role=combobox]), input[type=email], input[type=tel], input[type=number], input:not([type]), textarea")
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
        if combo.input_value() == ans: return True
        combo.click(); combo.fill(""); combo.type(ans, delay=15); time.sleep(1.0)
        opts = page.query_selector_all("[role=option]")
        names = [o.inner_text().strip() for o in opts]
        if ans in names:
            opts[names.index(ans)].click(); time.sleep(0.5)
            if combo.input_value() == ans: return True
            combo.click(); combo.fill(""); combo.type(ans, delay=15); time.sleep(1.0)
            for _ in range(names.index(ans) + 1): page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter"); time.sleep(0.5)
            if combo.input_value() == ans: return True
        page.keyboard.press("Escape"); return False
    if txt:
        if ans.startswith("__"): return False
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
    return False, "no confirmation seen (captcha?)"

# ---------------- Greenhouse (job-boards.greenhouse.io) ----------------
def fill_gh(page, job, log):
    url = job["url"]
    m = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url) or re.search(r"gh_jid=(\d+)", url)
    if m and len(m.groups()) == 2: url = f"https://job-boards.greenhouse.io/embed/job_app?for={m.group(1)}&token={m.group(2)}"
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
    for f in page.query_selector_all(".field-wrapper, fieldset, .checkbox, [class*=demographic] .select, .eeoc__question"):
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
        if re.search(r"cover letter|why .*(interested|join|us|company)|anything else|additional", label, re.I) and job.get("note"):
            ta = f.query_selector("textarea"); bt = f.query_selector("button:has-text('Enter manually')")
            if bt: bt.click(); time.sleep(0.3); ta = f.query_selector("textarea")
            if ta: ta.fill(job["note"]); continue
        try:
            ok = set_gh(page, f, ans)
        except Exception as e:
            ok = False; log(f"  ! {label[:60]}: {e}")
        if not ok and req: missing.append(label[:90])
    return missing

def set_gh(page, f, ans):
    if ans is None: return False
    sel = f.query_selector("input[role=combobox], .select__input input, [class*=select__control]")
    choices = f.query_selector_all("input[type=checkbox], input[type=radio]")
    txt = f.query_selector("input[type=text]:not([role=combobox]), input[type=email], input[type=tel], textarea")
    if sel:
        inp = f.query_selector("input[role=combobox]") or sel
        terms = {"__DECLINE__": ["decline", "prefer not", "don't wish", "not wish"], "__ACK__": ["yes", "i acknowledge", "acknowledge", "agree"],
                 "Company careers page": ["Company Website", "Company website", "Careers", "Website", "Job Board", "Other"]}.get(ans, [ans, ans[:12]])
        for term in terms:
            inp.click(timeout=4000); inp.fill(""); inp.type(term, delay=15); time.sleep(0.9)
            opts = page.query_selector_all("[role=option], .select__option")
            real = [o for o in opts if not re.search(r"no options|loading", o.inner_text(), re.I)]
            h = pick_option([(o.inner_text(), o) for o in real], term if ans == "Company careers page" else ans) or (real[0] if real and ans not in ("__DECLINE__",) and len(real) <= 3 else None)
            if ans == "__DECLINE__" and not h and real: h = pick_option([(o.inner_text(), o) for o in real], "__DECLINE__")
            if h:
                try: h.click(force=True, timeout=3000)
                except Exception:
                    idx = real.index(h)
                    for _ in range(idx): page.keyboard.press("ArrowDown")
                    page.keyboard.press("Enter")
                time.sleep(0.3); return True
            page.keyboard.press("Escape")
        return False
    if choices:
        opts = [(c.evaluate("e => (e.closest('label') || document.querySelector(`label[for='${e.id}']`) || e.parentElement).innerText"), c) for c in choices]
        h = pick_option(opts, ans)
        if h: h.check(force=True); return True
        return False
    if txt:
        if ans.startswith("__"): return False
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
        if re.search(r"thank you for applying|application (has been )?(received|submitted)|confirmation", body + u, re.I): return True, "success"
        if re.search(r"security code|verification code", body, re.I):
            ok = enter_email_code(page)
            if not ok: return False, "EMAIL CODE REQUIRED (timed out)"
            continue
        errs = page.query_selector_all(".helper-text--error, [id$=-error], .error")
        if errs and _ > 3: return False, "; ".join(e.inner_text()[:80] for e in errs[:5])
    return False, "no confirmation seen (captcha?)"

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    with in_workspace():
        run(json.load(open(argv[0])), dry="--dry" in argv)


def run(jobs, dry=False):
    os.makedirs("proof", exist_ok=True)
    results = []
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context("pw-profile", headless=False, viewport={"width": 1300, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for job in jobs:
            name = job.get("name") or job["url"]
            log = lambda s: print(s, flush=True)
            log(f"== {name}")
            try:
                ash = "ashbyhq" in job["url"]
                missing = fill_ashby(page, job, log) if ash else fill_gh(page, job, log)
                stamp = datetime.datetime.now().strftime("%m%d-%H%M%S")
                shot = f"proof/{re.sub(r'[^A-Za-z0-9]+', '_', name)[:50]}_{stamp}.png"
                if missing:
                    page.screenshot(path=shot, full_page=True)
                    status = "NEEDS YOU: " + " | ".join(missing)
                elif dry:
                    page.screenshot(path=shot, full_page=True); status = "filled (dry run)"
                else:
                    ok, msg = submit_ashby(page) if ash else submit_gh(page)
                    page.screenshot(path=shot, full_page=True)
                    status = ("SUBMITTED" if ok else "FAILED: ") + ("" if ok else msg)
            except Exception as e:
                status, shot = f"ERROR: {e}"[:200], ""
            log(f"   -> {status}")
            record("application", job=name, url=job["url"], status=status.split(":")[0], detail=status, proof=shot,
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
