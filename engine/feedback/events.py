"""Append-only event log: the raw signal for the feedback loop.

Every stage records what happened (job discovered, resume built, application submitted/failed,
email received). The memory layer ingests these events into the knowledge graph, and the
learning layer scores them against outcomes (reply, OA, interview, rejection).

File: workspace/events.jsonl  (one JSON object per line)
"""
import datetime, json, os

from engine.config import WORKSPACE


def record(kind, **fields):
    os.makedirs(WORKSPACE, exist_ok=True)
    ev = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "kind": kind, **fields}
    with open(os.path.join(WORKSPACE, "events.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return ev


def read(kind=None):
    path = os.path.join(WORKSPACE, "events.jsonl")
    if not os.path.exists(path):
        return []
    evs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    return [e for e in evs if kind is None or e["kind"] == kind]
