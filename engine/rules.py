"""The rules that drive the engine, as one catalog (v1.2): what each rule does, where it lives, and how often it fired.

Nothing here is a second copy of a rule. Every group is read from the module that runs it, so the catalog cannot
drift from the engine:

  title     engine/discovery/filters.py      a posting's title / location decides whether it is read at all
  gate      engine/tailoring/tailor.py       BLOCKERS, years, core stacks, mechanical roles: a JD that fails is skipped
  learned   workspace/learned_gate.json      phrases the rejection feedback promoted (blocking only with the clutch in)
  answers   engine/apply/runner.py RULES     how each form question is answered: a preset key, a fixed reply, a
                                             decline / acknowledge, or "you decide"
  safety    engine/safety.py + pipeline       airbags and limits that stop a job or a pass
  override  profile/override.json            the draft override (engine/override.py)

Answer sources come from the AST of runner.py (`P.get('work_auth_status')` -> "preset work_auth_status"), so the
catalog names WHERE an answer comes from and never shows the answer itself: no personal value leaves the bank.

Firing counts come from the event log: SKIPPED details for the gate, the [label, answer] pairs of recent applications
replayed through RULES for answers (first match wins, as in the filler), flag events for the airbags. Cost: O(L x R)
regex tests for L labels and R rules, cached for a minute so a page poll is a dict read.
"""
import ast, collections, inspect, json, os, re, time

from engine.config import WORKSPACE

LABELS_MAX = 400  # applications replayed for answer counts (newest first): bounded work per log change


def _source(node):
    """Where an answer rule's reply comes from, from its AST node (never the value)."""
    if isinstance(node, ast.Constant):
        v = node.value
        if v is None:
            return "you decide"
        return {"__ACK__": "acknowledge", "__DECLINE__": "decline", "__SKILLS__": "Fact Bank skills"}.get(v, f"fixed: {v}")
    keys = [n.args[0].value for n in ast.walk(node) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get"
            and n.args and isinstance(n.args[0], ast.Constant)]
    keys += [n.slice.value for n in ast.walk(node) if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)]
    if keys:
        return "preset " + " + ".join(dict.fromkeys(str(k) for k in keys))
    return "computed"


def _answer_rules():
    """runner.RULES with a readable pattern, its source and the comment above it, in matching order."""
    from engine.apply import runner
    tree = ast.parse(inspect.getsource(runner))
    lines = inspect.getsource(runner).splitlines()
    node = next(n.value for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "RULES")
    out = []
    for i, el in enumerate(node.elts):
        if not isinstance(el, ast.Tuple) or len(el.elts) < 2:
            continue
        why = lines[el.lineno - 2].strip() if el.lineno >= 2 else ""
        out.append({"id": f"answer-{i + 1}", "pattern": (el.elts[0].value if isinstance(el.elts[0], ast.Constant) else ast.unparse(el.elts[0]))[:220], "source": _source(el.elts[1]),
                    "note": why[1:].strip() if why.startswith("#") else "", "line": el.lineno})
    return out, runner


AIRBAGS = [("rate cap", r"submissions .{0,30}today|daily cap"), ("sensitive field", r"sensitive"),
           ("payment / fees", r"fee|payment|money"), ("answer drift", r"differs|drift|preset"),
           ("unexpected site", r"redirect|domain|left the|unexpected"), ("kill switch", r"kill|stop file|halt")]


def _airbag(detail):
    """A flag's free-text detail -> the airbag that raised it."""
    return next((n for n, p in AIRBAGS if re.search(p, detail, re.I)), "other")


_CACHE = {"key": None, "data": None, "at": 0.0}
TTL_S = 60


def _fires():
    """Firing counts per rule name from the event log, cached on the log's size."""
    from engine.feedback.events import read
    path = os.path.join(WORKSPACE, "events.jsonl")
    try:
        key = os.path.getsize(path)
    except OSError:
        key = 0
    # the log grows with every event: recount at most once a minute (a full replay is a few seconds)
    if _CACHE["key"] == key or (_CACHE["data"] and time.time() - _CACHE["at"] < TTL_S):
        return _CACHE["data"]
    gate, flags, answers, recent = collections.Counter(), collections.Counter(), collections.Counter(), []
    apps = []
    rules, runner = _answer_rules()
    compiled = [re.compile(p, re.I) for p, _ in runner.RULES]
    for e in read():
        k = e.get("kind")
        if k == "application" and e.get("status") == "SKIPPED" and str(e.get("detail", "")).startswith("JD:"):
            for b in str(e["detail"])[3:].split(","):
                b = b.strip(" []'\"")
                name = "years" if re.fullmatch(r"\d+\+ yrs", b) else b.split(":")[0] if b.startswith(("core stack", "learned")) else b
                gate[name] += 1
            recent.append({"ts": e.get("ts"), "group": "gate", "rule": str(e["detail"])[3:].strip()[:60], "job": e.get("job")})
        elif k == "application" and e.get("answers"):
            apps.append(e)
        elif k == "flag":
            flags[_airbag(str(e.get("detail") or e.get("reason") or ""))] += 1
    for e in apps[-LABELS_MAX:]:
        for pair in e.get("answers") or []:
            if not isinstance(pair, (list, tuple)) or not pair:
                continue
            l = " ".join(str(pair[0]).split()).lower()
            for j, rx in enumerate(compiled):
                if rx.search(l):
                    answers[j] += 1
                    break
        if e.get("status") == "SUBMITTED":
            recent.append({"ts": e.get("ts"), "group": "answers", "rule": f"{len(e.get('answers') or [])} answers", "job": e.get("job")})
    recent.sort(key=lambda r: r.get("ts") or "")
    data = {"gate": gate, "flags": flags, "answers": answers, "recent": recent[-24:][::-1], "apps_replayed": len(apps[-LABELS_MAX:])}
    _CACHE.update(key=key, data=data, at=time.time())
    return data


def catalog():
    """Every rule group with its rules, live state and firing counts (the /api/rules shape)."""
    from engine.discovery import filters as F
    from engine.tailoring import tailor as T
    from engine.gearbox import clutch_engaged
    from engine import override
    f = _fires()
    answers, runner = _answer_rules()
    for i, r in enumerate(answers):
        r["fires"] = f["answers"].get(i, 0)
    by_source = collections.Counter(("preset" if r["source"].startswith("preset") else r["source"].split(":")[0]) for r in answers)

    gate = [{"id": f"gate-{n}", "name": n, "pattern": p[:220], "fires": f["gate"].get(n, 0)} for n, p in T.BLOCKERS]
    gate += [
        {"id": "gate-years", "name": "years", "pattern": f"min years asked > {T.user_years()} (your preset)", "fires": f["gate"].get("years", 0)},
        {"id": "gate-stack", "name": "core stack", "pattern": "a required language the Fact Bank has none of: "
         + ", ".join(T.missing_stacks()), "fires": f["gate"].get("core stack", 0)},
        {"id": "gate-mech", "name": "mechanical / manufacturing role", "pattern": "2+ mechanical-design markers and no software stack",
         "fires": f["gate"].get("mechanical / manufacturing role", 0)},
    ]
    title = [
        {"id": "title-domain", "name": "software title", "pattern": "profile/domains.json title patterns (your lanes)"},
        {"id": "title-nonsw", "name": "non-software title", "pattern": F.NON_SOFTWARE.pattern[:220]},
        {"id": "title-noteng", "name": "not engineering", "pattern": F.NOT_ENGINEERING.pattern},
        {"id": "title-us", "name": "US location", "pattern": "US city / state / remote; non-US places dropped"},
    ]
    learned_path = os.path.join(WORKSPACE, "learned_gate.json")
    try:
        lg = json.load(open(learned_path, encoding="utf-8"))
    except (OSError, ValueError):
        lg = {}
    learned = [{"id": f"learned-{i}", "name": r.get("phrase"), "status": r.get("status"), "rejected": r.get("rejected"),
                "seen": r.get("seen"), "fires": f["gate"].get("learned", 0) if r.get("status") == "active" else 0}
               for i, r in enumerate(lg.get("rules", []))]
    from engine import safety as S
    flags = f["flags"]
    safety = [
        {"id": "safe-kill", "name": "kill switch", "pattern": "workspace/STOP or KILL halts before the next job and each submit"},
        {"id": "safe-sensitive", "name": "sensitive field", "pattern": S.SENSITIVE.pattern[:220]},
        {"id": "safe-payment", "name": "payment / fees", "pattern": S.PAYMENT.pattern[:220]},
        {"id": "safe-rate", "name": "rate cap", "pattern": f"{os.environ.get('REGEN_MAX_PER_DAY', '25')} per day, 3 per company per day"},
        {"id": "safe-drift", "name": "answer drift", "pattern": "a legal answer differs from your presets -> stop"},
        {"id": "safe-site", "name": "unexpected site", "pattern": "the form left the job's ATS -> stop"},
        {"id": "safe-ashby", "name": "Ashby pacing", "pattern": f"{os.environ.get('REGEN_ASHBY_PER_PASS', '1')} per pass (bot-flag cooldowns)"},
        {"id": "safe-captcha", "name": "human checks", "pattern": "captchas and 'are you a person' questions go to you, never solved"},
        {"id": "safe-trust", "name": "trust gate", "pattern": "employer legitimacy + scam signals before any data is shared"},
    ]
    for s in safety:
        s["fires"] = flags.get(s["name"], 0)
    try:
        ov = override.state()
    except Exception:
        ov = {}
    groups = [
        {"id": "title", "name": "Title filter", "stage": "discover", "where": "engine/discovery/filters.py",
         "about": "Decides whether a posting is read at all: software titles in your lanes, US locations.", "rules": title},
        {"id": "gate", "name": "Fit gate", "stage": "select", "where": "engine/tailoring/tailor.py",
         "about": "Reads the whole job description; any hard blocker skips the job before a resume is built.", "rules": gate},
        {"id": "learned", "name": "Learned from rejections", "stage": "select", "where": "workspace/learned_gate.json",
         "about": "Phrases the feedback loop found in rejected JDs. Only 'active' ones block, and only with the clutch in.",
         "rules": learned, "live": {"clutch": "in" if clutch_engaged() else "out"}},
        {"id": "answers", "name": "Form answers", "stage": "fill", "where": "engine/apply/runner.py RULES",
         "about": "First match wins. Legal and status answers come only from your presets; unknowns go to you.",
         "rules": answers, "live": {"saved_answers": len(runner.BANK), "by_source": dict(by_source),
                                     "apps_replayed": f["apps_replayed"]}},
        {"id": "safety", "name": "Airbags and limits", "stage": "submit", "where": "engine/safety.py",
         "about": "Checks that stop a job or a pass and flag you. They are not gears: speed never relaxes them.", "rules": safety},
        {"id": "override", "name": "Draft override", "stage": "fill", "where": "engine/override.py",
         "about": "Your standing 'draft' approval: drafts instead of parking, never invents facts or touches human checks.",
         "rules": [{"id": "override-draft", "name": "draft", "pattern": "on" if ov.get("draft") else "off",
                    "since": ov.get("since")}]},
    ]
    for g in groups:
        g["count"] = len(g["rules"])
        g["fires"] = sum(r.get("fires") or 0 for r in g["rules"])
    return {"groups": groups, "recent": f["recent"], "total": sum(g["count"] for g in groups)}
