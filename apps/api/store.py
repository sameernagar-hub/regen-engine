"""Where events come from. Postgres when REGEN_DATABASE_URL (or REGEN_DB_HOST + a password file) is set (see
migrate.py), otherwise the engine's own append-only workspace/events.jsonl. Both are read-only here: the engine stays
the only writer."""
import json, os

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


def backend():
    return "postgres" if DSN else "jsonl"


def read(after=0):
    """[(id, event)] with id > after, oldest first."""
    if DSN:
        import psycopg
        with psycopg.connect(DSN) as con:
            rows = con.execute("SELECT id, payload FROM events WHERE id > %s ORDER BY id", (after,)).fetchall()
        return [(i, p) for i, p in rows]
    out = []
    if not os.path.exists(EVENTS):
        return out
    with open(EVENTS, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if i <= after or not line.strip():
                continue
            try:
                out.append((i, json.loads(line)))
            except ValueError:
                continue
    return out


def size_marker():
    """Cheap change detector for the SSE loop."""
    if DSN:
        import psycopg
        with psycopg.connect(DSN) as con:
            return con.execute("SELECT coalesce(max(id), 0) FROM events").fetchone()[0]
    return os.path.getsize(EVENTS) if os.path.exists(EVENTS) else 0
