"""`python -m apps.api.migrate`: copy workspace/events.jsonl into Postgres, idempotently.

The table keeps the log's semantics: append-only (an UPDATE/DELETE trigger refuses changes), ordered by `id`, and each
line is stored once (unique sha256), so re-running after the engine appends more lines only adds the new ones.
"""
import hashlib, json, os, sys

from apps.api.store import DSN, EVENTS

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id       bigserial PRIMARY KEY,
  sha      char(64) UNIQUE NOT NULL,
  ts       timestamptz,
  kind     text NOT NULL,
  job      text,
  payload  jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS events_kind_ts ON events (kind, ts);
CREATE INDEX IF NOT EXISTS events_job ON events (job);
CREATE OR REPLACE FUNCTION events_append_only() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'events is append-only'; END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS events_no_change ON events;
CREATE TRIGGER events_no_change BEFORE UPDATE OR DELETE ON events FOR EACH ROW EXECUTE FUNCTION events_append_only();
"""


def main(argv=None):
    if not DSN:
        sys.exit("set REGEN_DATABASE_URL, e.g. postgresql://regen:regen@127.0.0.1:5433/regen")
    import psycopg
    added = 0
    with psycopg.connect(DSN) as con:
        con.execute(SCHEMA)
        with open(EVENTS, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                cur = con.execute(
                    "INSERT INTO events (sha, ts, kind, job, payload) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (sha) DO NOTHING",
                    (hashlib.sha256(line.encode()).hexdigest(), e.get("ts"), e.get("kind", "?"), e.get("job"), json.dumps(e)))
                added += cur.rowcount
        total = con.execute("SELECT count(*) FROM events").fetchone()[0]
    print(f"{added} new events -> postgres ({total} total)")


if __name__ == "__main__":
    main()
