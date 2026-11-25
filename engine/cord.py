"""Claude cord (11-24, user: "the agents can ask this Claude chat ... and vice versa"): a two-way line between the
engine's agents and the operator's Claude session, at zero API cost.

    agents -> Claude   ask(frm, text, ...)   Shadow when it abstains on a parked question, the supervisor on a new
                                             fleet problem, the orchestrator when a task lands in the dead letter.
                                             One open ask per key (a repeat while open is a no-op).
    Claude -> agents   reply(id, answer)     Claude answers over MCP (cord_reply). A reply to a question that carries
                                             a job saves the answer through the normal answer bank as Shadow (same
                                             override policy: legal / sponsorship stay per job, EEO decline-only,
                                             never invented facts), so the job retries with it.
    watching           `python -m engine cord watch`  prints each new open ask once: the Claude session runs it under
                                             a Monitor, so an ask wakes the chat instead of waiting for a human.

Files (workspace volume): cord/asks.jsonl, cord/replies.jsonl. Append-only, newline-delimited JSON; open asks =
asks without a reply. O(asks) per read; asks older than KEEP_S drop out of the open list.

    python -m engine cord [list]            open asks
    python -m engine cord reply <id> <answer>
    python -m engine cord watch [seconds]   stream new open asks (one line each)
"""
import json, os, sys, time

from engine.config import WORKSPACE

DIR = os.path.join(WORKSPACE, "cord")
ASKS = os.path.join(DIR, "asks.jsonl")
REPLIES = os.path.join(DIR, "replies.jsonl")
KEEP_S = 3 * 86400
KINDS = ("question", "problem", "dead_letter", "note")


def _read(path):
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def _append(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def open_asks(now=None, asks_path=None, replies_path=None):
    now = now or time.time()
    done = {r.get("id") for r in _read(replies_path or REPLIES)}
    return [a for a in _read(asks_path or ASKS) if a.get("id") not in done and now - a.get("t", 0) <= KEEP_S]


def ask(frm, text, kind="question", key=None, context=None, now=None, asks_path=None, replies_path=None):
    """Post an ask from an agent. Returns its id (the existing one when an ask with this key is still open)."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    now = now or time.time()
    key = key or f"{kind}:{' '.join(str(text).split())[:160].lower()}"
    for a in open_asks(now, asks_path, replies_path):
        if a.get("key") == key:
            return a["id"]
    aid = f"{frm}-{int(now * 1000)}"
    _append(asks_path or ASKS, {"id": aid, "t": now, "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
                                "from": frm, "kind": kind, "key": key, "text": str(text)[:600],
                                "context": context or {}})  # asks.jsonl is the record (no event: callers log their own)
    return aid


def reply(aid, answer, by="claude", asks_path=None, replies_path=None, save=None):
    """Claude's answer to an ask. A question with a job goes into the answer bank as Shadow (the job retries)."""
    a = next((x for x in _read(asks_path or ASKS) if x.get("id") == aid), None)
    if not a:
        return {"error": f"no ask {aid}"}
    if any(r.get("id") == aid for r in _read(replies_path or REPLIES)):
        return {"error": f"ask {aid} already has a reply"}
    out = {"id": aid, "answer": str(answer)[:2000], "by": by, "t": time.time()}
    ctx = a.get("context") or {}
    if a.get("kind") == "question" and ctx.get("job") and ctx.get("question"):
        try:
            if save is None:
                from engine.feedback.answers import save
            out["saved"] = save(ctx["job"], ctx["question"], answer, by="shadow")
        except ValueError as e:  # the override policy refused it (EEO, invented facts...): the ask stays open
            return {"error": f"answer refused: {e}"}
    _append(replies_path or REPLIES, out)
    try:
        from engine.feedback.events import record
        record("cord", action="reply", id=aid, by=by)
    except Exception:
        pass
    return out


def replies(limit=30, replies_path=None):
    return _read(replies_path or REPLIES)[-limit:]


def line(a):
    ctx = a.get("context") or {}
    job = f" [{ctx['job']}]" if ctx.get("job") else ""
    return f"CORD {a['id']} {a['kind']} from {a['from']}{job}: {a['text']}"


def main(argv):
    cmd = argv[0] if argv else "list"
    if cmd == "list":
        asks = open_asks()
        for a in asks:
            print(line(a))
        print(f"{len(asks)} open ask(s)")
    elif cmd == "reply" and len(argv) >= 3:
        print(json.dumps(reply(argv[1], " ".join(argv[2:]))))
    elif cmd == "watch":
        every = float(argv[1]) if len(argv) > 1 else 20
        seen = set()
        while True:
            for a in open_asks():
                if a["id"] not in seen:
                    seen.add(a["id"])
                    print(line(a), flush=True)
            time.sleep(every)
    else:
        raise SystemExit(__doc__)
