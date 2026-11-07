"""The agent graph (11-07): Shadow at the root, then agents, sub-agents and sub-sub-agents, each marked with who
owns it today. Ownership moves from the supervisor to Shadow one rung at a time (engine/shadow_brain.py LADDER):

    Shadow ─┬─ applier agents (one per applier container)          owner: supervisor until level 3
            │     └─ job agents (one per job in its claimed batch)  owner: engine until level 2
            │           └─ question agents (one per open question)  owner: Shadow (level 1: it answers as you)
            ├─ parked jobs (jobs waiting on a call)                 owner: Shadow from level 1
            │     └─ question agents, each with Shadow's answer and confidence
            └─ service agents (pipeline, answers, desk, ...)        owner: supervisor until level 4

The nodes are the engine's real workers (containers, batches, jobs, questions), not extra processes: the graph is
computed from heartbeats, batch files and Shadow's switchboard on each call, O(heartbeats + claimed jobs + lines).

plan() lists what Shadow would do now at each node (retry a job it can answer, scale appliers, requeue a lost batch)
and marks each action allowed or locked by the ladder; act() runs only the allowed ones. Nothing above Shadow's
earned level ever runs: a locked action is shown, never executed.
"""
import json, os, time

from engine.config import WORKSPACE

BOX = os.path.join(WORKSPACE, "batches")
APPLIER_MB = 650      # one applier (headed Chromium + filler) at gear 2, measured 10-21
RESERVE_MB = 1500     # what Shadow leaves free for Docker Desktop and the rest of the stack
HOST_MB = 7600


def _load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _owner(level, need, earned="shadow", before="supervisor"):
    return earned if level >= need else before


def graph(fleet=None, lines=None, level=None):
    """The nested agent tree as {id, kind, label, state, owner, children}. Inputs are injectable for tests."""
    from engine import shadow, shadow_brain
    if fleet is None:
        from engine.supervisor import fleet as _fleet
        fleet = _fleet()
    lines = shadow.lines() if lines is None else lines
    level = shadow_brain.ladder()["level"] if level is None else level
    open_lines = [l for l in lines if l.get("open")]
    by_job = {}
    for l in open_lines:
        by_job.setdefault(l.get("job"), []).append(l)

    def questions(job_lines):
        out = []
        for l in job_lines:
            for i, r in enumerate(l.get("recommend") or [{"q": l.get("question"), "a": None}]):
                out.append({"id": f"q:{l['url']}:{i}", "kind": "question", "label": str(r.get("q") or "")[:90],
                            "state": "answer ready" if r.get("a") else "abstains (yours)", "owner": "shadow",
                            "answer": r.get("a"), "conf": r.get("conf"), "strategy": r.get("strategy"), "children": []})
        return out

    appliers = []
    for m in fleet.get("members") or []:
        if m.get("role") != "applier" or not m.get("up"):
            continue
        jobs = []
        if m.get("batch"):
            for j in _load(os.path.join(BOX, "claimed", m["batch"]), []):
                name = j.get("name") or j.get("job") or "?"
                jobs.append({"id": f"job:{j.get('url') or name}", "kind": "job", "label": name[:80], "state": "applying",
                             "owner": _owner(level, 2, before="engine"), "children": questions(by_job.pop(name, []))})
        appliers.append({"id": f"applier:{m.get('host')}", "kind": "applier", "label": f"applier {str(m.get('host'))[:6]}",
                         "state": m.get("state") or "?", "owner": _owner(level, 3), "children": jobs})
    parked = [{"id": f"job:{ls[0]['url']}", "kind": "job", "label": str(job)[:80], "state": ls[0].get("state") or "parked",
               "owner": "shadow", "children": questions(ls)} for job, ls in by_job.items()]
    sup = next((m for m in fleet.get("members") or [] if m.get("role") == "supervisor"), {}) or {}
    services = [{"id": f"service:{name}", "kind": "service", "label": name, "state": st, "owner": _owner(level, 4),
                 "children": []} for name, st in sorted((sup.get("services") or {}).items())]
    for m in fleet.get("members") or []:
        if m.get("role") in ("pipeline", "answers", "desk", "feedback", "relay", "reposync") and \
                not any(s["label"] == m["role"] for s in services):
            services.append({"id": f"service:{m['role']}", "kind": "service", "label": m["role"],
                             "state": m.get("state") or ("up" if m.get("up") else "down"), "owner": _owner(level, 4), "children": []})
    groups = [
        {"id": "group:appliers", "kind": "group", "label": "Applier agents", "state": f"{len(appliers)} running",
         "owner": _owner(level, 3), "children": appliers},
        {"id": "group:parked", "kind": "group", "label": "Parked jobs", "state": f"{len(parked)} on a call",
         "owner": "shadow", "children": parked},
        {"id": "group:services", "kind": "group", "label": "Service agents", "state": f"{len(services)} services",
         "owner": _owner(level, 4), "children": services},
    ]
    st = shadow.settings()
    return {"id": "shadow", "kind": "shadow", "label": "Shadow", "state": f"mode {st['mode']}, level {level}",
            "owner": _owner(level, 5, before="you"), "children": groups}


def count(node):
    """{kind: n} over the whole tree."""
    out = {}
    stack = [node]
    while stack:
        n = stack.pop()
        out[n["kind"]] = out.get(n["kind"], 0) + 1
        stack.extend(n.get("children") or [])
    return out


def shadow_want(lo, hi, jobs, mem_mb=None):
    """Shadow's balance for appliers: one per 3 jobs (the supervisor's rule), capped by memory headroom so the host
    never swaps (10-24: 9 appliers hit 7.2 of 7.6 GB and screenshots timed out). O(1)."""
    want = max(lo, min(hi, -(-jobs // 3)))
    if mem_mb is not None:
        room = max(0, HOST_MB - RESERVE_MB - mem_mb)
        want = min(want, max(lo, room // APPLIER_MB + 1))
    return want


def plan(fleet=None, lines=None, level=None):
    """What Shadow would do now: [{"action", "target", "why", "needs_level", "allowed"}]."""
    from engine import shadow_brain
    if fleet is None:
        from engine.supervisor import fleet as _fleet
        fleet = _fleet()
    if lines is None:
        from engine import shadow
        lines = shadow.lines()
    level = shadow_brain.ladder()["level"] if level is None else level
    out = []
    for l in lines:
        if l.get("open") and l.get("recommend") and all(r.get("a") for r in l["recommend"]):
            out.append({"action": "retry", "target": l.get("job"), "why": "Shadow has a confident answer for every open question",
                        "needs_level": 2})
    for n in fleet.get("stale_claims") or []:
        out.append({"action": "requeue", "target": n, "why": "batch lost with its container", "needs_level": 2})
    running = sum(1 for m in fleet.get("members") or [] if m.get("role") == "applier" and m.get("up"))
    try:
        from engine.supervisor import desired
        from engine import gearbox
        lo, hi = gearbox.appliers() or (1, 3)
        _, jobs = desired(lo, hi)
        mem = (_load(os.path.join(WORKSPACE, "containers.json"), {}).get("totals") or {}).get("mem_mb")
        want = shadow_want(lo, hi, jobs, mem)
        if want != running:
            out.append({"action": "scale", "target": f"appliers {running} -> {want}",
                        "why": f"{jobs} jobs waiting; memory used {mem} MB", "needs_level": 3})
    except Exception:
        pass
    for a in out:
        a["allowed"] = level >= a["needs_level"]
    return out


def act(fleet=None, lines=None, level=None):
    """Run the allowed actions (today: job retries at level 2+). Scaling at level 3+ is applied by the supervisor
    through shadow_want(). Returns the plan with "done" set on what ran."""
    from engine.feedback.events import record
    p = plan(fleet, lines, level)
    retry = [a["target"] for a in p if a["action"] == "retry" and a["allowed"]]
    if retry:
        from engine import shadow
        n = shadow._retry_as_shadow(retry[:shadow.MAX_PICKUPS])
        for a in p:
            if a["action"] == "retry" and a["allowed"] and a["target"] in retry[:shadow.MAX_PICKUPS]:
                a["done"] = True
        record("shadow", action="agent_retry", jobs=n)
    return p
