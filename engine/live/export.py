"""`python -m engine site [days=7]`: build the public face of the project (site/), safe to publish.

The public page is the live view in demo mode: it replays the engine's real recent activity, anonymized.
  kept:     role titles, stages, outcomes (confirmation / interview / ...), skip reasons, safety stops, counts
  removed:  company names (-> "a company"), anything waiting on the candidate, answers, URLs, emails, proofs, files
Re-run it (the daily task does) and push: Render redeploys the static site automatically.
"""
import json, os, re, sys, time
from datetime import datetime, timedelta

from engine.config import ROOT, WORKSPACE
from engine.live.server import HERE, narrate, snapshot

SITE = os.path.join(ROOT, "site")


def anonymize(text, company):
    if company:
        text = re.sub(re.escape(company), "a company", text, flags=re.I)
    text = re.sub(r"https?://\S+|\S+@\S+", "", text)
    # skip reasons can reveal personal status (citizenship, visa, clearance). Publicly, they become generic categories.
    m = re.match(r"(Let a company go: )(.*)\.$", text)
    if m:
        r, cats = m.group(2).lower(), []
        if re.search(r"citizen|sponsor|clearance|itar|polygraph|export", r):
            cats.append("eligibility requirements")
        if re.search(r"\d+\+ yrs", r):
            cats.append("seniority")
        if "grad window" in r:
            cats.append("graduation window")
        text = m.group(1) + (" and ".join(cats) or "not a fit") + "."
    return text[:1].upper() + text[1:]


def build(days=7):
    cut = (datetime.now() - timedelta(days=days)).isoformat()
    events = []
    path = os.path.join(WORKSPACE, "events.jsonl")
    rows = []
    for line in open(path, encoding="utf-8") if os.path.exists(path) else []:
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    # a later correction supersedes earlier application events for the same job: show only the corrected record
    corrected = {(e.get("job"), e.get("kind")): i for i, e in enumerate(rows) if e.get("correction")}
    for i, e in enumerate(rows):
        if e.get("ts", "") < cut or e.get("backfilled"):
            continue
        if (e.get("job"), e.get("kind")) in corrected and i < corrected[(e.get("job"), e.get("kind"))]:
            continue
        n = narrate(e)
        if not n or n["tone"] == "you":           # what's waiting on the candidate stays private
            continue
        co = e.get("company") or (e.get("job") or "").partition(" - ")[0].strip()
        events.append({"stage": n["stage"], "tone": n["tone"], "text": anonymize(n["text"], co), "ts": e["ts"][:16]})
    # visitors read it, so "your" becomes "the"; identical lines in a row collapse ("7 companies confirmed ...")
    merged = []
    for ev in events:
        ev["text"] = re.sub(r"\byour\b", "the", ev["text"])
        if merged and merged[-1]["text"].endswith(ev["text"].replace("A company", "", 1)) and ev["text"].startswith("A company"):
            merged[-1]["n"] = merged[-1].get("n", 1) + 1
            merged[-1]["text"] = f"{merged[-1]['n']} companies" + ev["text"].replace("A company", "", 1)
            continue
        merged.append(ev)
    events = merged
    s = snapshot()
    roles = [[role, lane] for _co, role, lane in s.get("verified_jobs", [])]  # role + lane only, never the company
    data = {"generated": time.strftime("%Y-%m-%d %H:%M"), "days": days, "verified": s["verified"],
            "verified_roles": roles, "boards": s["boards"], "events": events[-160:]}
    # airbag: refuse to publish if any company name we've ever touched would appear on the public page
    raw = json.dumps(data, ensure_ascii=False).lower()
    names = set()
    for line in open(path, encoding="utf-8") if os.path.exists(path) else []:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        c = (e.get("company") or (e.get("job") or "").partition(" - ")[0]).strip().lower()
        if len(c) >= 3:
            names.add(c)
    leaks = sorted(c for c in names if re.search(r"(?<![a-z])" + re.escape(c) + r"(?![a-z])", raw))
    if leaks:
        raise SystemExit(f"refusing to build site/: company names would be public: {leaks}")
    os.makedirs(SITE, exist_ok=True)
    json.dump(data, open(os.path.join(SITE, "replay.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    page = open(os.path.join(HERE, "index.html"), encoding="utf-8").read()
    page = page.replace("<script>", "<script>window.REGEN_DEMO = true;</script>\n<script>", 1)
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(page)
    return data


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    d = build(int(argv[0]) if argv else 7)
    print(f"site/ ready: {len(d['events'])} anonymized events, {d['verified']} verified applications")


if __name__ == "__main__":
    main()
