"""Shadow's two-call handoff (11-06). Policy: engine/override.py (the gates treat Shadow, the user's AI delegate, as
the user; Shadow stays truthful; it never touches a CAPTCHA).

When a job parks on a question (NEEDS YOU), the engine calls the user, twice, with a timer behind each call:

    parked ──► call 1 ──(ring_min)──► call 2 ──(ring_min)──► Shadow picks up: the job is retried with Shadow
                  │                      │                    answering as the user
                  └── you pick up ───────┴──► the job is yours (answer it on Needs you, or press Pick up)

You pick up by answering any of the job's questions (Needs you / MCP answer_save by="user") or with POST
/api/shadow/pickup. Modes: "calls" (the above), "always" (Shadow answers on the form itself, nothing parks: the old
`draft on`), "off" (calls ring, Shadow never picks up). Human checks (CAPTCHA, bot checks) never ring: they wait on
the Desk.

State: workspace/shadow_calls.json {url: {job, parked, call1, call2, by, done}}; every transition is a `shadow` event.
tick() runs in the answers container every 30 s: O(parked jobs) with no network calls; at most MAX_PICKUPS retries
per tick so a backlog never floods the appliers.
"""
import json, os, time

from engine.config import WORKSPACE

CALLS = os.path.join(WORKSPACE, "shadow_calls.json")
MODES = ("calls", "always", "off")
RING_MIN = 5          # minutes between parking, call 1, call 2 and Shadow's pickup
WINDOW_H = 48         # jobs parked longer ago than this never ring (the old backlog stays on Needs you)
MAX_PICKUPS = 15


def _load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(path, data):
    tmp = path + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, path)  # atomic


def settings():
    """{"mode", "ring_min"}. An older override.json with only {"draft": true} reads as "always"."""
    from engine import override
    s = override.state()
    mode = s.get("mode") or ("always" if s.get("draft") else "off")
    return {"mode": mode if mode in MODES else "off", "ring_min": float(s.get("ring_min") or RING_MIN)}


def configure(mode=None, ring_min=None, note=""):
    from engine import override
    s = override.state()
    if mode is not None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {', '.join(MODES)}")
        s["mode"], s["draft"] = mode, mode == "always"  # override.on() is True only when Shadow answers inline
    if ring_min is not None:
        ring_min = float(ring_min)
        if not 0.5 <= ring_min <= 240:
            raise ValueError("ring_min must be between 0.5 and 240 minutes")
        s["ring_min"] = ring_min
    s.update(since=time.strftime("%Y-%m-%dT%H:%M:%S"), by="user", note=note or s.get("note", ""))
    os.makedirs(os.path.dirname(override.PATH), exist_ok=True)
    _save(override.PATH, s)
    from engine.feedback.events import record
    record("shadow", action="configure", mode=s.get("mode"), ring_min=s.get("ring_min"))
    return settings()


def _parked(now):
    """{url: (job, parked_epoch, detail)} for jobs whose latest status is NEEDS YOU, parked within WINDOW_H, on a
    question (not a human check)."""
    from engine.feedback.events import read
    from engine.override import HUMAN_CHECK
    out = {}
    for e in read("application"):
        u = e.get("url")
        if not u:
            continue
        if e.get("status") != "NEEDS YOU":
            out.pop(u, None)
            continue
        try:
            t = time.mktime(time.strptime(e["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
        except (KeyError, ValueError):
            continue
        if now - t <= WINDOW_H * 3600 and not HUMAN_CHECK.search(e.get("detail") or ""):
            out[u] = (e.get("job") or "?", t, e.get("detail") or "")
    return out


def _answered_by_you(job, since):
    from engine.feedback.events import read
    for kind in ("answer_queued", "answer"):
        for e in read(kind):
            if e.get("job") == job and e.get("source", "user") != "shadow" and (e.get("ts") or "") >= since:
                return True
    return False


def tick(now=None):
    """Advance every line one step: ring call 1, ring call 2, or hand the job to Shadow. Returns counts."""
    from engine.feedback.events import record
    now = now or time.time()
    st, calls = settings(), _load(CALLS, {})
    ring = st["ring_min"] * 60
    stamp = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))
    counts, pickups = {"call1": 0, "call2": 0, "shadow": 0, "you": 0}, []
    parked = _parked(now)
    for u in [u for u, c in calls.items() if not c.get("done") and u not in parked]:
        calls[u]["done"] = True  # submitted / skipped / retried meanwhile: the line goes quiet
    for u, (job, t, detail) in parked.items():
        c = calls.get(u)
        if c and c.get("done") and c.get("parked", 0) >= t:
            continue  # this parking was already handled (Shadow tried, or you took it)
        if not c or c.get("parked", 0) < t:  # newly parked (or parked again after a retry): call 1
            if c and c.get("by") == "shadow":
                continue  # Shadow already picked this one up once and it parked again: it is yours now
            calls[u] = c = {"job": job, "parked": t, "call1": now, "call2": None, "by": None, "done": False,
                            "question": detail.replace("NEEDS YOU: ", "")[:300]}
            record("shadow", action="call1", job=job, url=u)
            counts["call1"] += 1
            continue
        if _answered_by_you(job, stamp(c["call1"])):
            c.update(by="you", done=True)
            record("shadow", action="pickup", by="you", job=job, url=u)
            counts["you"] += 1
        elif not c.get("call2") and now - c["call1"] >= ring:
            c["call2"] = now
            record("shadow", action="call2", job=job, url=u)
            counts["call2"] += 1
        elif c.get("call2") and now - c["call2"] >= ring and st["mode"] in ("calls", "always") and len(pickups) < MAX_PICKUPS:
            c.update(by="shadow", done=True, picked=now)
            record("shadow", action="pickup", by="shadow", job=job, url=u)
            pickups.append(job)
            counts["shadow"] += 1
    _save(CALLS, calls)
    if pickups:
        _retry_as_shadow(pickups)
    return counts


def _retry_as_shadow(jobs):
    """One batch in batches/inbox for these jobs, each flagged shadow=True: the runner answers them as the user."""
    from engine.feedback.answer_queue import BOX, find_entry, job_extras
    out = []
    for job in jobs:
        e = find_entry(job)
        try:  # the same title / location filter as answer retries: a non-US or non-SWE role is never retried
            from engine.discovery.filters import keep, load_domain
            if keep(load_domain(), str(job).split(" - ", 1)[-1], "United States", "") not in (None, "location", "non-US"):
                e = None
        except Exception:
            pass
        if e:
            e["shadow"] = True
            mine = job_extras().get(job)
            if mine:
                e["extra"] = {**(e.get("extra") or {}), **mine}
            out.append(e)
    if out:
        os.makedirs(os.path.join(BOX, "inbox"), exist_ok=True)
        name = f"shadow_{time.strftime('%Y%m%d_%H%M%S')}.json"
        tmp = os.path.join(BOX, "inbox", "." + name)
        json.dump(out, open(tmp, "w", encoding="utf-8"), indent=1)
        os.replace(tmp, os.path.join(BOX, "inbox", name))
    return len(out)


def pickup(url, who="you"):
    """Answer a ringing line by hand: who="you" keeps the job for you; who="shadow" hands it to Shadow now."""
    from engine.feedback.events import record
    calls = _load(CALLS, {})
    c = calls.get(url)
    if not c or c.get("done"):
        raise KeyError("no call is ringing for that job")
    c.update(by=who, done=True, picked=time.time())
    _save(CALLS, calls)
    record("shadow", action="pickup", by=who, job=c["job"], url=url)
    if who == "shadow":
        _retry_as_shadow([c["job"]])
    return c


def lines(now=None, limit=60):
    """The switchboard: open lines first (call 1 / call 2 with seconds to the next step), then recent pickups."""
    now = now or time.time()
    ring = settings()["ring_min"] * 60
    out = []
    for u, c in _load(CALLS, {}).items():
        if c.get("done"):
            state, next_s = f"picked up by {c.get('by') or 'nobody'}" if c.get("by") else "closed", None
        elif c.get("call2"):
            state, next_s = "call 2", max(0, round(c["call2"] + ring - now))
        else:
            state, next_s = "call 1", max(0, round(c["call1"] + ring - now))
        out.append({"url": u, "job": c.get("job"), "question": c.get("question"), "state": state, "by": c.get("by"),
                    "next_s": next_s, "open": not c.get("done"),
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(c.get("picked") or c.get("call2") or c.get("call1") or now))})
    out.sort(key=lambda x: (not x["open"], x["next_s"] if x["open"] else 0, x["ts"]), reverse=False)
    opened = [x for x in out if x["open"]]
    closed = sorted([x for x in out if not x["open"]], key=lambda x: x["ts"], reverse=True)
    return (opened + closed)[:limit]


def oversight(hours=24):
    """For the supervisor: Shadow's mode, lines ringing, and who answered in the last `hours` (applications by
    answered_by: you / shadow / engine, and saved answers by source). O(events)."""
    from engine.feedback.events import read
    since = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - hours * 3600))
    apps, answers = {}, {}
    for e in read("application"):
        if (e.get("ts") or "") >= since and e.get("answered_by") and e.get("status") in ("SUBMITTED", "NEEDS YOU", "FAILED"):
            k = f"{e['answered_by']}:{e['status']}"
            apps[k] = apps.get(k, 0) + 1
    for kind in ("answer", "answer_queued"):
        for e in read(kind):
            if (e.get("ts") or "") >= since:
                src = "shadow" if e.get("source") == "shadow" else "you"
                answers[src] = answers.get(src, 0) + 1
    st = status()
    return {"mode": st["mode"], "ringing": st["ringing"], "picked_by_shadow": st["by_shadow"], "picked_by_you": st["by_you"],
            "applications": apps, "answers": answers}


def status(now=None):
    ls = lines(now)
    return {**settings(), "lines": ls, "ringing": sum(1 for x in ls if x["open"]),
            "by_shadow": sum(1 for x in ls if x["by"] == "shadow"), "by_you": sum(1 for x in ls if x["by"] == "you")}
