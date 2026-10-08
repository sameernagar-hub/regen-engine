"""Append-only event log: the raw signal for the feedback loop.

Every stage records what happened (job discovered, resume built, application submitted/failed,
email received). The memory layer ingests these events into the knowledge graph, and the
learning layer scores them against outcomes (reply, OA, interview, rejection).

File: workspace/events.jsonl  (one JSON object per line)

Concurrency (fixed 2026-10-07): several engine processes write here at once (batch builder, applier, scan).
On Windows, Python's append mode is "seek to end, then write", so two writers could overwrite each other's
bytes mid-line (two resume records were cut that way). record() now holds an exclusive lock on a sidecar
file (events.jsonl.lock) and writes the whole line with one os.write on an O_APPEND descriptor.

Reads are incremental: read() keeps the parsed events and the byte offset it reached, and on the next call
parses only bytes appended since (O(new lines) instead of O(whole file) per call). The runner calls it once
per job for the rate cap and the already-submitted check, so a batch was O(jobs x events); now it's O(events)
once plus O(new) per job. A malformed line is skipped (and counted), never fatal.
"""
import datetime, json, os

from engine.config import WORKSPACE

try:
    import msvcrt

    def _lock(fd):
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)  # blocks (retries for ~10 s, then raises)

    def _unlock(fd):
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
except ImportError:  # POSIX
    import fcntl

    def _lock(fd):
        fcntl.flock(fd, fcntl.LOCK_EX)

    def _unlock(fd):
        fcntl.flock(fd, fcntl.LOCK_UN)


def _path():
    return os.path.join(WORKSPACE, "events.jsonl")


def append_line(path, obj):
    """Append one JSON line atomically with respect to other engine processes."""
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    lf = os.open(path + ".lock", os.O_RDWR | os.O_CREAT)
    try:
        _lock(lf)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0))
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
    finally:
        try:
            _unlock(lf)
        finally:
            os.close(lf)


def record(kind, **fields):
    os.makedirs(WORKSPACE, exist_ok=True)
    ev = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "kind": kind, **fields}
    append_line(_path(), ev)
    return ev


_cache = {"path": None, "offset": 0, "events": [], "bad": 0, "ino": None}


def read(kind=None):
    path = _path()
    if not os.path.exists(path):
        return []
    st = os.stat(path)
    c = _cache
    if c["path"] != path or st.st_size < c["offset"] or c["ino"] != (st.st_ino, st.st_dev) and st.st_ino:
        c.update(path=path, offset=0, events=[], bad=0, ino=(st.st_ino, st.st_dev))  # new or truncated file: start over
    if st.st_size > c["offset"]:
        with open(path, "rb") as fh:
            fh.seek(c["offset"])
            chunk = fh.read()
        end = chunk.rfind(b"\n") + 1  # a line still being written is left for the next call
        for line in chunk[:end].splitlines():
            if not line.strip():
                continue
            try:
                c["events"].append(json.loads(line))
            except ValueError:
                c["bad"] += 1
        c["offset"] += end
    evs = c["events"]
    return list(evs) if kind is None else [e for e in evs if e.get("kind") == kind]


def bad_lines():
    """How many malformed lines read() skipped (shown by `engine status`)."""
    read()
    return _cache["bad"]
