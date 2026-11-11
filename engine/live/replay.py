"""`python -m engine replay [YYYY-MM-DD]`: one day of the live view, written down so it can be played back.

ALIVE Phase 0 (docs/ALIVE_PLAN.md §5). Writes workspace/replays/<date>.jsonl: one line per typed live event
(engine.live.server narrate() / signal()), in ledger order, scrubbed with the public feed's privacy rules
(engine/live/export.py), so the same file can feed "While you were away" (Phase 4) and the public site:

  kept:     kind, stage, tone, ts, text with every employer name replaced, generic skip categories, Shadow confidence,
            an opaque chip id per posting (same posting -> same id within the day, so chips can be followed)
  removed:  company names, URLs, answers and the questions waiting on you (tone "you" and shadow.abstain lines carry
            no text detail), emails, problem texts, hosts

If any employer name the ledger has ever touched would still appear, nothing is written (the export airbag).
O(E) per call.
"""
import hashlib, json, os, sys, time

from engine.config import WORKSPACE
from engine.live.export import anonymize, company_names, leaked, masker
from engine.live.server import narrate, signal

DIR = os.path.join(WORKSPACE, "replays")
KEEP_DETAIL = {"gear", "keywords", "cap", "targeting", "shadow.mode", "outcome"}  # details that are settings, not people


def chip(job, day):
    """Opaque, day-salted id for one posting: follows a chip across stages without naming it."""
    return hashlib.sha256(f"{day}|{job}".encode()).hexdigest()[:10] if job else None


def scrub(e, day, mask):
    """One ledger event -> a public-safe typed line, or None (internal / dry / not shown)."""
    n, sig = narrate(e), None
    if not n:
        sig = signal(e)
        if not sig:
            return None
    t = n or sig
    co = (n or {}).get("company") or e.get("company") or (e.get("job") or "").partition(" - ")[0].strip()
    out = {"ts": (e.get("ts") or "")[:19], "kind": t["kind"]}
    if n:
        out.update(stage=n["stage"], tone=n["tone"], job=chip(n.get("job"), day))
        if n.get("jobs"):
            out["n_jobs"] = len(n["jobs"])
        if n.get("conf") is not None:
            out["conf"] = n["conf"]
        if n["tone"] == "you" or n["kind"] == "shadow.abstain":
            out["text"] = "Something is waiting on the candidate."  # never the question: it can be personal
        else:
            out["text"] = mask(anonymize(n["text"], co))
            if n["kind"] == "gate.skip":
                out["detail"] = out["text"].split(": ", 1)[-1].rstrip(".")  # anonymize() made it a generic category
    else:
        out["text"] = mask(anonymize(sig["text"], co)) if sig["kind"] not in ("problem", "problem.clear") else (
            "A warning light came on." if sig["kind"] == "problem" else "A warning light went out.")
    if t["kind"] in KEEP_DETAIL and t.get("detail"):
        out["detail"] = str(t["detail"])
    if t.get("by") in ("shadow", "you", "user", "desk"):
        out["by"] = t["by"]
    return out


def build(day=None, events=None, names=None):
    """The scrubbed lines for one day (default today). events/names can be passed for tests. -> list of dicts."""
    day = day or time.strftime("%Y-%m-%d")
    if events is None:
        from engine.feedback.events import read
        events = read()
    names = company_names() if names is None else names
    mask = masker(names)
    rows = [r for e in events if (e.get("ts") or "").startswith(day) and not e.get("dry") for r in [scrub(e, day, mask)] if r]
    # every field but the generated ones: chip ids are hex hashes and ts is a date, so a short numeric or hex-like
    # employer name ("540") would match inside them without anything leaking
    bad = leaked([{k: v for k, v in r.items() if k not in ("job", "ts")} for r in rows], names)
    if bad:
        raise SystemExit(f"refusing to write the replay: employer names would be in it: {len(bad)} name(s)")
    return rows


def write(day=None):
    """Write workspace/replays/<day>.jsonl atomically. Returns (path, lines)."""
    day = day or time.strftime("%Y-%m-%d")
    rows = build(day)
    os.makedirs(DIR, exist_ok=True)
    path = os.path.join(DIR, f"{day}.jsonl")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return path, len(rows)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path, n = write(argv[0] if argv else None)
    print(f"replay: {n} events -> {os.path.relpath(path, WORKSPACE)}")
