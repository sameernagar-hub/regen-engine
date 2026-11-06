"""Outcome learning for bullet wordings (11-05, user: "it keeps learning ... a feedback loop").

Each resume event records which wording of each fact went out (qa.picks: fid -> variant index). When the inbox later
labels that application (engine/feedback/rejections.labeled: positive = OA / interview / offer, or rejection),
every wording on that resume gets one vote. weights() turns the votes into a small score that tailor() adds to the
JD match when it ranks facts and wordings: enough to break ties and nudge toward wordings that got replies, never
enough to override what the JD asks for (at most +/- MAX).

  refresh()  recount from the event log -> workspace/variant_stats.json (O(events))
  weights()  {"fid#i": weight}, re-read only when the file changes

Smoothing: weight = MAX * (pos - REJ_W * rej) / (pos + rej + PRIOR), so one rejection barely moves anything and a
wording needs repeated evidence before it counts. Rejections are common for every resume (most say nothing about
the resume), so they weigh less than a positive reply.
"""
import json
import os
import time

MAX, PRIOR, REJ_W = 0.9, 4.0, 0.25
_CACHE = {"mtime": None, "w": {}}


def _path():
    from engine.config import WORKSPACE
    return os.path.join(WORKSPACE, "variant_stats.json")


def refresh():
    from engine.feedback.events import read
    from engine.feedback.rejections import labeled
    picks = {}
    for e in read("resume"):
        p = (e.get("qa") or {}).get("picks")
        if p:
            picks[e["job"]] = p  # latest resume per job wins
    votes = {}
    n = {"positive": 0, "rejection": 0}
    for job, _, label in labeled():
        if label == "pending" or job not in picks:
            continue
        n[label] += 1
        for fid, i in picks[job].items():
            v = votes.setdefault(f"{fid}#{i}", {"pos": 0, "rej": 0})
            v["pos" if label == "positive" else "rej"] += 1
    w = {k: round(MAX * (v["pos"] - REJ_W * v["rej"]) / (v["pos"] + v["rej"] + PRIOR), 3) for k, v in votes.items()}
    out = {"updated": time.strftime("%Y-%m-%d %H:%M"), "labeled": n, "votes": votes, "weights": w}
    tmp = _path() + ".tmp"
    json.dump(out, open(tmp, "w"), indent=1)
    os.replace(tmp, _path())
    return out


def weights():
    try:
        m = os.path.getmtime(_path())
    except OSError:
        return {}
    if m != _CACHE["mtime"]:
        try:
            _CACHE.update(mtime=m, w=json.load(open(_path())).get("weights", {}))
        except (OSError, ValueError):
            _CACHE.update(mtime=m, w={})
    return _CACHE["w"]


if __name__ == "__main__":
    r = refresh()
    print(f"variant stats: {r['labeled']} labeled applications, {len(r['weights'])} wordings scored")
