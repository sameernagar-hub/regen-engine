"""`python -m apps.api.migrate [--loop SECONDS]`: copy workspace/events.jsonl into Postgres, idempotently.

The `events` table keeps the log's semantics: append-only (an UPDATE/DELETE trigger refuses changes), ordered by `id`,
and each line is stored once (unique sha256), so re-running after the engine appends more lines only adds the new ones.
events.jsonl stays the source of truth; the database is a labeled, queryable copy of it:

  events            every line, with kind + schema version (`v`, 1 when the event has none) as columns
  applications      kind=application: company, title, status, detail, url, proof, resume
  answers           kind=answer: question, pattern, source
  codes             kind=code: slug, latency_s
  outcomes          kind=outcome: company, outcome, subject, sender
  resumes           kind=resume: lane, file, coverage
  discoveries       kind=discovered: ats, source, lag_min
  supervisor_audit  kind=supervisor: action, target, jobs, want
  fleet_heartbeats  latest workspace/fleet/*.json per container (a table, upserted each pass; not events)

The per-kind relations are views over `events`, so they can never disagree with it. Every insert also fires
NOTIFY regen_events: the API's /api/stream LISTENs on it, so new events reach the browser without polling.
"""
import glob, hashlib, json, os, sys, time
from datetime import datetime, timezone

from apps.api.store import DSN, EVENTS
from engine.config import WORKSPACE

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id       bigserial PRIMARY KEY,
  sha      char(64) UNIQUE NOT NULL,
  ts       timestamptz,
  kind     text NOT NULL,
  job      text,
  payload  jsonb NOT NULL
);
ALTER TABLE events ADD COLUMN IF NOT EXISTS v smallint NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS events_kind_ts ON events (kind, ts);
CREATE INDEX IF NOT EXISTS events_job ON events (job);
CREATE OR REPLACE FUNCTION events_append_only() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'events is append-only'; END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS events_no_change ON events;
CREATE TRIGGER events_no_change BEFORE UPDATE OR DELETE ON events FOR EACH ROW EXECUTE FUNCTION events_append_only();
-- the data bus: every committed insert wakes the API's LISTEN (one notification per transaction, payload = max id)
CREATE OR REPLACE FUNCTION events_notify() RETURNS trigger AS $$
BEGIN PERFORM pg_notify('regen_events', (SELECT coalesce(max(id), 0)::text FROM new_rows)); RETURN NULL; END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS events_bus ON events;
CREATE TRIGGER events_bus AFTER INSERT ON events REFERENCING NEW TABLE AS new_rows
  FOR EACH STATEMENT EXECUTE FUNCTION events_notify();

CREATE OR REPLACE VIEW applications AS
  SELECT id, ts, job, split_part(job, ' - ', 1) AS company, substr(job, length(split_part(job, ' - ', 1)) + 4) AS title,
         payload->>'status' AS status, payload->>'detail' AS detail, payload->>'url' AS url,
         payload->>'proof' AS proof, payload->>'resume' AS resume, coalesce((payload->>'dry')::boolean, false) AS dry, v
  FROM events WHERE kind = 'application';
CREATE OR REPLACE VIEW answers AS
  SELECT id, ts, job, payload->>'question' AS question, payload->>'pattern' AS pattern, payload->>'source' AS source, v
  FROM events WHERE kind = 'answer';
CREATE OR REPLACE VIEW codes AS
  SELECT id, ts, payload->>'slug' AS slug, (payload->>'latency_s')::numeric AS latency_s, v
  FROM events WHERE kind = 'code';
CREATE OR REPLACE VIEW outcomes AS  -- latest record per message wins; "void" retracts (same rule as events.read)
  SELECT id, ts, company, outcome, subject, sender, jobs, v FROM (
    SELECT DISTINCT ON (COALESCE(payload->>'msg_id', id::text)) id, ts, payload->>'company' AS company,
           payload->>'outcome' AS outcome, payload->>'subject' AS subject, payload->>'sender' AS sender,
           payload->'jobs' AS jobs, v
    FROM events WHERE kind = 'outcome' ORDER BY COALESCE(payload->>'msg_id', id::text), id DESC) last
  WHERE outcome <> 'void';
CREATE OR REPLACE VIEW resumes AS
  SELECT id, ts, job, payload->>'lane' AS lane, payload->>'file' AS file, payload->'coverage' AS coverage, v
  FROM events WHERE kind = 'resume';
CREATE OR REPLACE VIEW discoveries AS
  SELECT id, ts, job, payload->>'ats' AS ats, payload->>'source' AS source, (payload->>'lag_min')::numeric AS lag_min, v
  FROM events WHERE kind = 'discovered';
CREATE OR REPLACE VIEW supervisor_audit AS
  SELECT id, ts, payload->>'action' AS action, payload->>'target' AS target, (payload->>'jobs')::int AS jobs,
         (payload->>'want')::int AS want, payload, v
  FROM events WHERE kind = 'supervisor';

CREATE TABLE IF NOT EXISTS fleet_heartbeats (
  host     text PRIMARY KEY,
  role     text,
  state    text,
  batch    text,
  seen     timestamptz,
  payload  jsonb NOT NULL
);
"""


def _row(line):
    """(sha, ts, kind, job, v, payload) for one jsonl line, or None when it is not JSON."""
    try:
        e = json.loads(line)
    except ValueError:
        return None
    if not isinstance(e, dict):
        return None
    v = e.get("v", 1)
    return (hashlib.sha256(line.encode()).hexdigest(), e.get("ts"), e.get("kind", "?"), e.get("job"),
            v if isinstance(v, int) else 1, json.dumps(e))


def copy_events(con, offset=0):
    """Insert lines after byte `offset`; returns (added, new_offset). A partial last line is left for the next pass."""
    if not os.path.exists(EVENTS):
        return 0, 0
    if os.path.getsize(EVENTS) < offset:  # file replaced or truncated: rescan, the sha keeps it idempotent
        offset = 0
    rows = []
    with open(EVENTS, "rb") as fh:
        fh.seek(offset)
        for raw in fh:
            if not raw.endswith(b"\n"):
                break
            offset += len(raw)
            line = raw.decode("utf-8", "replace").strip()
            if line and (r := _row(line)):
                rows.append(r)
    added = 0
    with con.cursor() as cur:
        for r in rows:
            cur.execute("INSERT INTO events (sha, ts, kind, job, v, payload) VALUES (%s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (sha) DO NOTHING", r)
            added += cur.rowcount
    return added, offset


def copy_heartbeats(con):
    n = 0
    for path in glob.glob(os.path.join(WORKSPACE, "fleet", "*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                hb = json.load(fh)
        except (OSError, ValueError):
            continue
        host = hb.get("host") or os.path.basename(path)[:-5]
        seen = datetime.fromtimestamp(hb["ts"], timezone.utc) if isinstance(hb.get("ts"), (int, float)) else None
        con.execute("INSERT INTO fleet_heartbeats (host, role, state, batch, seen, payload) VALUES (%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (host) DO UPDATE SET role=EXCLUDED.role, state=EXCLUDED.state, batch=EXCLUDED.batch, "
                    "seen=EXCLUDED.seen, payload=EXCLUDED.payload",
                    (host, hb.get("role"), hb.get("state"), hb.get("batch"), seen, json.dumps(hb)))
        n += 1
    return n


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not DSN:
        sys.exit("set REGEN_DATABASE_URL (e.g. postgresql://regen:regen@127.0.0.1:5433/regen) or REGEN_DB_HOST")
    loop = float(argv[argv.index("--loop") + 1]) if "--loop" in argv else 0
    import psycopg
    offset, ready = 0, False
    while True:
        try:
            with psycopg.connect(DSN) as con:
                if not ready:
                    con.execute(SCHEMA)
                added, moved = copy_events(con, offset)
                hosts = copy_heartbeats(con)
                total = con.execute("SELECT count(*) FROM events").fetchone()[0]
            ready, offset = True, moved  # only after the commit: a rolled-back pass is re-read
            if added or not loop:
                print(f"{added} new events -> postgres ({total} total, {hosts} heartbeats)", flush=True)
        except psycopg.OperationalError as exc:  # database still starting or restarting: try again next pass
            if not loop:
                raise
            print(f"ledger: postgres unavailable ({exc.__class__.__name__}), retrying", flush=True)
        if not loop:
            return
        time.sleep(loop)


if __name__ == "__main__":
    main()
