"""Where events come from. Postgres when REGEN_DATABASE_URL (or REGEN_DB_HOST + a password file) is set (see
migrate.py), otherwise the engine's own append-only workspace/events.jsonl. Both are read-only here: the engine stays
the only writer.

The log only grows, so reads are incremental (v1.2): rows already read stay in memory and each call fetches only
rows newer than the last id (Postgres) or byte offset (jsonl). A poll costs O(new rows) instead of O(log); before,
every request re-read ~12k payloads over a fresh connection (1 s for /api/human). A shrinking log (ledger rebuild,
truncated file) resets the cache. `version()` is (generation, last id), so callers can memoize work per log state (it carries a generation that changes on every reset)."""
import bisect, json, os, threading

from engine.config import WORKSPACE


def _dsn():
    """REGEN_DATABASE_URL wins; else build one from REGEN_DB_HOST and the Docker secret file, so the password never
    sits in an environment variable (the bank stack mounts it at /run/secrets/pg_password)."""
    url = os.environ.get("REGEN_DATABASE_URL")
    if url or not os.environ.get("REGEN_DB_HOST"):
        return url
    path = os.environ.get("REGEN_DB_PASSWORD_FILE", "/run/secrets/pg_password")
    try:
        with open(path, encoding="utf-8") as fh:
            pw = fh.read().strip()
    except OSError:
        return None
    from urllib.parse import quote
    user, db = os.environ.get("REGEN_DB_USER", "regen"), os.environ.get("REGEN_DB_NAME", "regen")
    return f"postgresql://{user}:{quote(pw, safe='')}@{os.environ['REGEN_DB_HOST']}:5432/{db}"


DSN = _dsn()
EVENTS = os.path.join(WORKSPACE, "events.jsonl")

_LOCK = threading.Lock()
_C = {"ids": [], "rows": [], "offset": 0, "line": 0, "con": None, "gen": 0, "src": None}


def backend():
    return "postgres" if DSN else "jsonl"


def _reset():
    """Forget every cached row. `gen` changes, so memos keyed on version() can't mistake new rows for old ones."""
    _C.update(ids=[], rows=[], offset=0, line=0, gen=_C["gen"] + 1)


def _query(sql, args=()):
    """One long-lived connection (reconnects once if the database restarted)."""
    import psycopg
    for attempt in (0, 1):
        try:
            if _C["con"] is None or _C["con"].closed:
                _C["con"] = psycopg.connect(DSN, autocommit=True)
            return _C["con"].execute(sql, args).fetchall()
        except psycopg.OperationalError:
            _C["con"] = None
            if attempt:
                raise


def _sync():
    """Append rows newer than what is cached. Caller holds _LOCK."""
    src = DSN or EVENTS
    if src != _C["src"]:
        _C["src"] = src
        _reset()  # another log (tests point EVENTS elsewhere)
    if DSN:
        last = _C["ids"][-1] if _C["ids"] else 0
        if last and _query("SELECT coalesce(max(id), 0) FROM events")[0][0] < last:
            _reset()  # the ledger was rebuilt: ids restarted
            last = 0
        for i, p in _query("SELECT id, payload FROM events WHERE id > %s ORDER BY id", (last,)):
            _C["ids"].append(i)
            _C["rows"].append((i, p))
        return
    try:
        size = os.path.getsize(EVENTS)
    except OSError:
        _reset()
        return
    if size < _C["offset"]:
        _reset()  # truncated or replaced
    if size == _C["offset"]:
        return
    with open(EVENTS, "rb") as fh:
        fh.seek(_C["offset"])
        chunk = fh.read()
    end = chunk.rfind(b"\n") + 1  # a half-written last line waits for the next call
    for raw in chunk[:end].split(b"\n")[:-1]:
        _C["line"] += 1
        if not raw.strip():
            continue
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        _C["ids"].append(_C["line"])
        _C["rows"].append((_C["line"], ev))
    _C["offset"] += end


def read(after=0):
    """[(id, event)] with id > after, oldest first. The list is a fresh slice; the event dicts are shared, read-only."""
    with _LOCK:
        _sync()
        return _C["rows"][bisect.bisect_right(_C["ids"], after):]


def version():
    """(generation, newest id) after a sync: a cheap key for memoizing work over the log. The generation changes on
    every reset, so a rebuilt log that reuses ids never matches an old key."""
    with _LOCK:
        _sync()
        return (_C["gen"], _C["ids"][-1] if _C["ids"] else 0)


def size_marker():
    """Cheap change detector for the SSE loop."""
    if DSN:
        with _LOCK:
            return _query("SELECT coalesce(max(id), 0) FROM events")[0][0]
    return os.path.getsize(EVENTS) if os.path.exists(EVENTS) else 0
