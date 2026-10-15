"""Workday filler + the desk: a visible browser the user signs in to, that the engine then fills forms in.

    python -m engine desk                 the desk container's loop (noVNC at http://127.0.0.1:6080)
    python -m engine desk --fill <url>    queue one reach-list job for the desk (the /reach page does the same)

Workday puts every application behind a candidate account per employer (tenant). Creating that account and typing
its password is the user's job, never the engine's. So the desk is one long-lived headed Chromium with a persistent
profile on its own volume (regen-desk): the user opens it through noVNC, signs in to a tenant once, and the session
cookie stays. When a fill request lands in workspace/desk/inbox/, the desk opens the posting in a new tab, walks the
wizard (My Information, My Experience, Application Questions, Voluntary Disclosures, Self Identify, Review) and fills
every field it can answer from presets + Fact Bank with the same answer() the other fillers use.

It stops, with the tab left open for the user, when:
  - the tenant asks to sign in or create an account ("NEEDS YOU: sign in"),
  - a required field has no answer from presets / Fact Bank ("NEEDS YOU: <labels>"),
  - it reaches Review: submit is the user's click unless REGEN_WORKDAY_SUBMIT=1 and nothing was missing (the
    standing auto-submit policy applies only when every required answer came from presets / Fact Bank).
Every result is an `application` event (status FILLED / NEEDS YOU / SUBMITTED / FAILED) plus the desk heartbeat.
Selectors are Workday's own data-automation-id attributes, the stable part of its markup across tenants.
"""
import datetime, json, os, re, sys, time

from engine.config import WORKSPACE

DESK = os.path.join(WORKSPACE, "desk")
INBOX = os.path.join(DESK, "inbox")
SUBMIT = os.environ.get("REGEN_WORKDAY_SUBMIT", "0") == "1"
MAX_STEPS = 9

AID = lambda a: f"[data-automation-id='{a}']"
APPLY = AID("adventureButton")
MANUAL = AID("applyManually")
NEXT = ", ".join(AID(a) for a in ("pageFooterNextButton", "bottom-navigation-next-button"))
SUBMIT_BTN = ", ".join(AID(a) for a in ("pageFooterSubmitButton", "bottom-navigation-submit-button")) + \
    ", button:has-text('Submit')"
SIGN_IN = ", ".join(AID(a) for a in ("signInContent", "signInForm", "createAccountLink", "signInLink",
                                     "createAccountSubmitButton", "password"))
SIGN_STEP = re.compile(r"sign in|create account|log ?in", re.I)  # the wizard's first step on most tenants
DECLINE_COOKIES = AID("legalNoticeDeclineButton")
ERRORS =", ".join(AID(a) for a in ("errorMessage", "inputAlert")) + ", [role=alert]"
FILE = AID("file-upload-input-ref") + ", input[type=file]"
DONE = re.compile(r"thank(s| you) for (applying|your application)|application (has been |was )?(submitted|received)|"
                  r"you('ve| have) (successfully )?applied", re.I)
# fixed fields of "My Information": automation id -> preset key (presets.json), filled only when empty
FIXED = {"legalNameSection_firstName": "first_name", "legalNameSection_lastName": "last_name",
         "addressSection_addressLine1": "address_line1", "addressSection_city": "city",
         "addressSection_postalCode": "zip", "email": "email", "phone-number": "phone"}


def request(url, name=None, resume=None, kind="fill"):
    """Queue one desk request (atomic write): kind "fill" (walk the form) or "open" (open a Workday employer's site
    and press Sign In, for the user to sign in). Returns the request path."""
    os.makedirs(INBOX, exist_ok=True)
    key = re.sub(r"[^A-Za-z0-9]+", "_", url)[-80:]
    path = os.path.join(INBOX, key + ".json")
    tmp = os.path.join(INBOX, "." + key + ".json")
    json.dump({"url": url, "name": name or url, "resume": resume, "kind": kind, "ts": time.time()},
              open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, path)
    return path


def _label(page, el):
    """The question text for one control: its formField container's label/legend, else aria-label."""
    return (el.evaluate("""e => { const w = e.closest("[data-automation-id^='formField-'], fieldset, li, div");
        const l = w && w.querySelector('label, legend'); return (l ? l.innerText : '') || e.getAttribute('aria-label') || ''; }""")
            or "").replace("*", "").strip()


def _required(el):
    return bool(el.evaluate("""e => { const w = e.closest("[data-automation-id^='formField-'], fieldset") || e;
        return e.required || e.getAttribute('aria-required') === 'true' || !!w.querySelector('abbr[title=required], [aria-required=true]')
               || /\\*/.test((w.querySelector('label, legend') || {}).innerText || ''); }"""))


def fill_page(page, job, log):
    """Fill every empty control on the current wizard page. Returns the labels of required fields left empty."""
    from engine.apply.runner import P, answer, pick_option
    missing = []
    for aid, key in FIXED.items():
        el = page.query_selector(AID(aid))
        if el and P.get(key) and not (el.input_value() or "").strip():
            el.fill(str(P[key]).replace("+1 ", "") if key == "phone" else str(P[key]))
    if job.get("resume"):
        f = page.query_selector(FILE)
        if f and not page.query_selector(AID("file-upload-successful")) and not job.get("_uploaded"):
            f.set_input_files(job["resume"])
            job["_uploaded"] = True
            page.wait_for_timeout(3000)  # Workday parses the resume into the experience sections
    fixed = {AID(a) for a in FIXED}
    for el in page.query_selector_all("input[type=text]:visible, input:not([type]):visible, textarea:visible, input[type=number]:visible, "
                                     "input[type=email]:visible, input[type=tel]:visible, input[type=url]:visible"):
        if any(el.evaluate(f"e => e.matches(\"{s}\")") for s in fixed) or (el.input_value() or "").strip():
            continue
        label = _label(page, el)
        if not label:
            continue
        ans = answer(label, job)
        job.setdefault("_answers", []).append([label[:200], ans])
        if ans and not str(ans).startswith("__"):
            el.fill(str(ans)); log(f"   . {label[:60]} -> {str(ans)[:30]}")
        elif _required(el):
            missing.append(label[:90])
    for btn in page.query_selector_all("button[aria-haspopup=listbox]:visible"):
        cur = (btn.inner_text() or "").strip()
        if cur and not re.fullmatch(r"select one|select|choose", cur, re.I):
            continue
        label = _label(page, btn)
        ans = answer(label, job)
        job.setdefault("_answers", []).append([label[:200], ans])
        h = None
        if ans:
            btn.click(); page.wait_for_timeout(400)
            opts = [(o.inner_text().strip(), o) for o in page.query_selector_all("[role=option]:visible")]
            h = pick_option(opts, str(ans)) if opts else None
            if h:
                h.click(); log(f"   . {label[:60]} -> {str(ans)[:30]}")
            else:
                page.keyboard.press("Escape")
        if not h and _required(btn):
            missing.append(label[:90])
    for grp in page.query_selector_all("fieldset:visible"):
        radios = grp.query_selector_all("input[type=radio]")
        if not radios or any(r.is_checked() for r in radios):
            continue
        legend = grp.query_selector("legend")
        label = (legend.inner_text() if legend else "").replace("*", "").strip()
        ans = answer(label, job)
        job.setdefault("_answers", []).append([label[:200], ans])
        opts = [((r.evaluate("e => (e.labels[0] || {}).innerText || e.value") or "").strip(), r) for r in radios]
        h = pick_option(opts, str(ans)) if ans else None
        if h:
            h.check(); log(f"   . {label[:60]} -> {str(ans)[:30]}")
        elif _required(grp):
            missing.append(label[:90])
    for box in page.query_selector_all("input[type=checkbox]:visible"):  # terms / consent boxes
        if box.is_checked():
            continue
        label = _label(page, box)
        ans = answer(label, job)
        if ans == "__ACK__" or ans == "Yes":
            box.check(); job.setdefault("_answers", []).append([label[:200], "checked"])
        elif _required(box):
            missing.append(label[:90])
    return missing


def walk(page, job, log, submit=SUBMIT):
    """Posting -> Apply -> Apply Manually -> every wizard step. Returns the final status string."""
    page.goto(job["url"], wait_until="domcontentloaded")
    try:  # the posting is rendered by script after the shell loads
        page.wait_for_selector(", ".join((APPLY, MANUAL, NEXT, SIGN_IN)), timeout=20000)
    except Exception:
        pass
    if page.query_selector(DECLINE_COOKIES):  # the most private cookie choice (functional cookies only)
        try:
            page.click(DECLINE_COOKIES, timeout=3000)
        except Exception:
            pass
    if page.query_selector(APPLY):
        page.click(APPLY)
        try:  # the Apply menu (Autofill with Resume / Apply Manually / Use My Last Application) is a popup
            page.wait_for_selector(MANUAL, timeout=8000)
        except Exception:
            pass
    if page.query_selector(MANUAL):
        page.click(MANUAL); page.wait_for_timeout(2500)
    for step in range(MAX_STEPS):
        try:  # each step renders after its data loads: wait for a button, a sign-in control or the confirmation
            page.wait_for_selector(", ".join((NEXT, SUBMIT_BTN, SIGN_IN)), timeout=20000)
        except Exception:
            pass
        active = page.query_selector(AID("progressBarActiveStep"))
        if page.query_selector(SIGN_IN) or active and SIGN_STEP.search(active.inner_text() or ""):
            host = re.sub(r"^https?://([^/]+).*", r"\1", page.url)
            return f"NEEDS YOU: sign in to {host} in the desk (http://127.0.0.1:6080), then press Fill again"
        body = page.inner_text("body")
        if DONE.search(body):
            return "SUBMITTED"
        missing = fill_page(page, job, log)
        if missing:
            return "NEEDS YOU: " + " | ".join(missing)
        sub = page.query_selector(SUBMIT_BTN)
        nxt = page.query_selector(NEXT)
        if sub and (not nxt or "submit" in (nxt.inner_text() or "").lower()):
            if job.get("resume") and not job.get("_uploaded"):
                return "NEEDS YOU: the resume was never attached (no upload field seen); attach it in the desk"
            if not submit:
                return "FILLED: review and submit in the desk (http://127.0.0.1:6080)"
            from engine import safety
            if safety.stop_requested():
                return "STOPPED: kill switch before submit"
            sub.click()
            for _ in range(30):
                page.wait_for_timeout(1000)
                if DONE.search(page.inner_text("body")):
                    return "SUBMITTED"
            return "FAILED: no confirmation seen after submit"
        if not nxt:
            return "FAILED: no Next or Submit button on step " + str(step + 1)
        nxt.click(); page.wait_for_timeout(2500)
        errs = [e.inner_text().strip()[:80] for e in page.query_selector_all(ERRORS) if e.is_visible()]
        if errs:
            return "NEEDS YOU: " + " | ".join(errs[:5])
    return "FAILED: more than %d wizard steps" % MAX_STEPS


# ---------------- SmartRecruiters (in the desk only) ----------------
# The one-page "Easy apply" form (jobs.smartrecruiters.com/oneclick-ui/...) is behind a DataDome bot check: in an
# unattended applier it answers "An error occurred". In the desk the user is at the screen: if the check appears,
# they solve it, and the engine fills. The engine never tries to get around the check, and never clicks the final
# Submit here (the user does, after looking at the filled form).
SR_APPLY = "a#st-apply, a:has-text(\"I'm interested\"), button:has-text(\"I'm interested\")"
BOT_CHECK = "iframe[src*='captcha-delivery'], iframe[src*='datadome'], iframe[src*='hcaptcha'], iframe[src*='recaptcha']"
SR_SUBMIT = "button:has-text('Submit'), button[type=submit]:has-text('Apply'), spl-button:has-text('Submit')"


def walk_sr(page, job, log):
    """Posting -> Easy apply form -> fill from presets + Fact Bank + resume upload. Returns the status string."""
    page.goto(job["url"], wait_until="domcontentloaded")
    try:
        page.wait_for_selector(SR_APPLY, timeout=20000)
        page.click(SR_APPLY)
    except Exception:
        pass
    try:
        page.wait_for_selector(", ".join(("input[type=email]", "input[type=file]", BOT_CHECK)), timeout=25000)
    except Exception:
        pass
    if page.query_selector(BOT_CHECK) or re.search(r"an error occurred, please try again", page.inner_text("body"), re.I):
        return "NEEDS YOU: SmartRecruiters shows a human check in the desk (http://127.0.0.1:6080); solve it, then press Fill again"
    missing = []
    for _ in range(3):  # the form may reveal more questions after the first answers / a Next step
        missing = fill_page(page, job, log)
        nxt = page.query_selector("button:has-text('Next'):visible, spl-button:has-text('Next')")
        if missing or not nxt:
            break
        nxt.click(); page.wait_for_timeout(2500)
    if job.get("resume") and not job.get("_uploaded"):
        f = page.query_selector("input[type=file]")
        if f:
            f.set_input_files(job["resume"]); job["_uploaded"] = True; page.wait_for_timeout(3000)
        else:
            return "NEEDS YOU: no resume upload field found; attach the resume in the desk"
    if missing:
        return "NEEDS YOU: " + " | ".join(missing)
    if not page.query_selector(SR_SUBMIT):
        return "FAILED: filled, but no Submit button found (check the form in the desk)"
    return "FILLED: review and submit in the desk (http://127.0.0.1:6080)"


def open_signin(page, url):
    """Open a Workday employer's site and press its Sign In button: the user signs in (or creates the account)."""
    page.goto(url, wait_until="domcontentloaded")
    try:
        page.wait_for_selector(AID("utilityButtonSignIn"), timeout=20000)
        page.click(AID("utilityButtonSignIn"))
        return "opened sign-in"
    except Exception:
        return "opened (no Sign In button found: use the page's own menu)"


def handle(ctx, req, log=print):
    """One request in a fresh tab of the desk's browser; the tab stays open for the user. A fill records the event."""
    from engine.feedback.events import record
    page = ctx.new_page()
    page.set_default_timeout(15000)
    if req.get("kind") == "open":
        try:
            st = open_signin(page, req["url"])
        except Exception as e:
            st = f"open failed: {str(e)[:80]}"
        log(f"desk: {req.get('name')} -> {st}")
        return st
    job = {"name": req.get("name") or req["url"], "url": req["url"], "resume": req.get("resume"), "extra": {}}
    if job["resume"] and not os.path.isabs(job["resume"]):
        job["resume"] = os.path.join(WORKSPACE, job["resume"].replace("\\", "/"))
    try:
        status = (walk_sr if "smartrecruiters.com" in job["url"] else walk)(page, job, log)
    except Exception as e:
        status = f"FAILED: {str(e)[:160]}"
    shot = ""
    try:
        os.makedirs(os.path.join(WORKSPACE, "proof"), exist_ok=True)
        shot = f"proof/{re.sub(r'[^A-Za-z0-9]+', '_', job['name'])[:50]}_{datetime.datetime.now():%m%d-%H%M%S}.png"
        page.screenshot(path=os.path.join(WORKSPACE, shot), full_page=True)
    except Exception:
        shot = ""
    log(f"desk: {job['name'][:60]} -> {status}")
    record("application", job=job["name"], url=job["url"], status=status.split(":")[0], detail=status, proof=shot,
           answers=job.get("_answers"), drafted=job.get("_drafted"), resume=req.get("resume"), dry=False, by="desk")
    return status


def loop(poll=3):
    """The desk container: one persistent browser, fill requests from workspace/desk/inbox, heartbeat every poll."""
    from playwright.sync_api import sync_playwright
    from engine.supervisor import beat
    os.makedirs(INBOX, exist_ok=True)
    prof = os.environ.get("REGEN_DESK_PROFILE", "/home/regen/desk-profile")
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(prof, headless=False, no_viewport=True,
                                                    args=["--window-position=0,0", "--window-size=1366,900",
                                                          "--disable-background-timer-throttling"])
        home = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            home.goto("http://api:8787/", wait_until="domcontentloaded", timeout=10000)
        except Exception:
            pass
        last = "ready"
        while True:
            reqs = sorted(f for f in os.listdir(INBOX) if f.endswith(".json") and not f.startswith("."))
            beat("desk", state="filling" if reqs else "ready", queued=len(reqs), last=last[:80], tabs=len(ctx.pages))
            for f in reqs[:1]:
                path = os.path.join(INBOX, f)
                try:
                    req = json.load(open(path, encoding="utf-8"))
                except (OSError, ValueError):
                    req = None
                os.remove(path)
                if req and req.get("url"):
                    last = handle(ctx, req)
            for p in ctx.pages[1:][:-10]:  # keep the 10 newest tabs for the user (sign-ins, filled forms); older ones close
                try:
                    p.close()
                except Exception:
                    pass
            time.sleep(poll)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--fill" in argv:
        url = argv[argv.index("--fill") + 1]
        from engine.discovery.reach import load
        row = next((r for r in load() if r.get("url") == url), {})
        print(request(url, f"{row.get('company', '')} - {row.get('title', '')}".strip(" -") or None, row.get("resume")))
        return
    loop()


if __name__ == "__main__":
    main()
