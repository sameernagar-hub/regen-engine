"""Oil change (v1.2): the engine's deep clean, shown as an oil-filter change in the control room (/oilchange).

    python -m engine oilchange [--status | --now | --dry]

The hourly clean (engine/clean.py) is the top-up. The oil change is the service: it drains what the hourly clean does
not reach and reports every stage live, so the web page can animate it while it runs.

Stages, in order (each one is logged with what it found and what it removed):
  drain    workspace: everything engine/clean.py's retention policy marks old (proofs past 90 d, resumes past 3 d,
           JD cache, logs, codes, batches, dead heartbeats, browser caches), then proofs are shrunk in place
  filter   mailbox: Greenhouse security-code mail older than 2 days and job-alert mail (exact alert senders) older
           than 7 days moves to Bin (Gmail keeps Bin 30 days, so it is undoable; starred mail is never touched; All Mail is never expunged)
  flush    Docker: dangling images, build cache beyond CACHE_KEEP_GB (least recently used first), and idle appliers whose memory grew past
           REGEN_OIL_APPLIER_MB (drained with the supervisor's handshake, so a batch is never cut off)
  refill   queue: postings older than REGEN_OIL_QUEUE_DAYS (45) and jobs with a final status leave queue.json
  check    dipstick: inspect again and record the oil life after the change

Oil life (0-100) = 100 - max(wear, worst contaminant). Wear is the share of the service interval (24 h) since the last
change; each contaminant is its amount over its limit (workspace 400 MB reclaimable, build cache 6 GB, 300 old mails,
300 stale postings, an idle applier at the memory limit). The supervisor inspects every 5 minutes (Docker and the
mailbox at most every 30) and changes the oil when life reaches 10 or below, i.e. once a day, sooner when something
fills up. The web page or `--now` can ask for a change at any time (workspace/oilchange.request).

Never touched: profile/ (Fact Bank, presets, answers), events.jsonl, named volumes, other compose projects' containers,
images in use, starred or recent mail. Stopped containers of other projects are reported, never removed. O(files +
mail matched + containers) per change.
"""
import datetime, json, os, sys, threading, time
from urllib.parse import quote

from engine.config import WORKSPACE

STATE = os.path.join(WORKSPACE, "oilchange.json")
REQUEST = os.path.join(WORKSPACE, "oilchange.request")
STAGES = ("drain", "filter", "flush", "refill", "check")
INTERVAL_H = float(os.environ.get("REGEN_OIL_INTERVAL_H", "24"))
CHANGE_AT = float(os.environ.get("REGEN_OIL_CHANGE_AT", "10"))  # oil life at or below this: change now
QUEUE_DAYS = float(os.environ.get("REGEN_OIL_QUEUE_DAYS", "45"))
APPLIER_MB = float(os.environ.get("REGEN_OIL_APPLIER_MB", "1400"))
CACHE_KEEP_GB = float(os.environ.get("REGEN_OIL_CACHE_KEEP_GB", "2"))  # build cache kept after a change (newest first)
LIMITS = {"workspace_mb": 400, "build_cache_gb": 6, "old_mail": 300, "stale_queue": 300, "applier_mb": APPLIER_MB}
SLOW_EVERY = 1800  # Docker /system/df and IMAP searches: at most every 30 min while inspecting
# Gmail search syntax (X-GM-RAW). Exact alert senders only, never a whole platform domain: 10-27 a domain-wide query
# caught recruiter InMail notifications (restored to the Inbox). The engine has already harvested these alerts.
# The sender list is mailbox config, so it lives in the private profile (profile/alert_senders.json, a JSON list of
# addresses); without it the alerts query is skipped.
def _alert_senders():
    from engine.config import PROFILE
    try:
        return tuple(json.load(open(os.path.join(PROFILE, "alert_senders.json"), encoding="utf-8")))
    except (OSError, ValueError):
        return ()


ALERT_SENDERS = _alert_senders()
MAIL_QUERIES = {"codes": "from:greenhouse-mail.io subject:(security code) older_than:2d -is:starred"}
if ALERT_SENDERS:
    MAIL_QUERIES["alerts"] = "(" + " OR ".join(f"from:{a}" for a in ALERT_SENDERS) + ") older_than:7d -is:starred"
MAIL_MAX = 500  # per query per change: a light pass, the next change takes the rest


def load():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"history": []}


def save(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, default=str)
    os.replace(tmp, STATE)  # the API never reads half a file


def _posted(p, today=None):
    """Queue `posted` is "MM-DD" (or ISO). Returns a date, assuming the most recent year that is not in the future."""
    today = today or datetime.date.today()
    try:
        if len(p) >= 10:
            return datetime.date.fromisoformat(p[:10])
        m, d = map(int, p.split("-")[:2])
        dt = datetime.date(today.year, m, d)
        return dt if dt <= today + datetime.timedelta(days=1) else dt.replace(year=today.year - 1)
    except (TypeError, ValueError, AttributeError):
        return None


def stale_queue(queue, today=None):
    """Queue jobs a change removes: posted more than QUEUE_DAYS ago, or holding a final status. O(Q)."""
    from engine.pipeline import latest_status
    today = today or datetime.date.today()
    cut = today - datetime.timedelta(days=QUEUE_DAYS)
    st = latest_status()
    out = []
    for j in queue:
        d = _posted(j.get("posted") or "", today)
        if (d and d < cut) or st.get(j.get("url")) in ("SUBMITTED", "SKIPPED", "FLAGGED", "FAILED"):
            out.append(j)
    return out


def _queue():
    try:
        return json.load(open(os.path.join(WORKSPACE, "queue.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return []


# ---------------- mailbox (IMAP, same .env app password as engine/notify.py) ----------------
def _imap():
    import imaplib
    from engine.notify import _env
    e = _env()
    if not (e.get("REGEN_SMTP_USER") and e.get("REGEN_SMTP_APP_PASSWORD")):
        return None
    m = imaplib.IMAP4_SSL(e.get("REGEN_IMAP_HOST", "imap.gmail.com"))
    m.login(e["REGEN_SMTP_USER"], e["REGEN_SMTP_APP_PASSWORD"])
    return m


def _search(m, query):
    typ, data = m.uid("SEARCH", "X-GM-RAW", '"' + query + '"')  # the queries hold no double quotes
    return data[0].split() if typ == "OK" and data and data[0] else []


def mail(move=False):
    """{query name: matched count} (and moved count when move=True). Moving is COPY from All Mail into Bin: Gmail
    then shows the mail only in Bin. All Mail is never expunged (that would be a permanent delete)."""
    m = _imap()
    if not m:
        return {"skipped": "no IMAP credentials"}
    out = {}
    try:
        typ, _ = m.select('"[Gmail]/All Mail"', readonly=not move)
        if typ != "OK":
            return {"skipped": "no All Mail folder"}
        for name, q in MAIL_QUERIES.items():
            uids = _search(m, q)
            out[name] = len(uids)
            if move and uids:
                batch = uids[:MAIL_MAX]
                typ, _ = m.uid("COPY", b",".join(batch).decode(), '"[Gmail]/Bin"')
                out[name + "_moved"] = len(batch) if typ == "OK" else 0
    finally:
        try:
            m.logout()
        except Exception:
            pass
    return out


# ---------------- Docker (supervisor only: it holds the socket) ----------------
def _docker_ok():
    from engine.supervisor import SOCK
    return os.path.exists(SOCK)


def docker_df():
    """Build cache total / reclaimable bytes and dangling images, from /system/df. ~1-3 s."""
    from engine.supervisor import _docker
    df = _docker("GET", "/system/df?type=build-cache&type=image") or {}
    cache = df.get("BuildCache") or []
    imgs = df.get("Images") or []
    dangling = [i for i in imgs if (i.get("RepoTags") in (None, [], ["<none>:<none>"])) and not i.get("Containers")]
    return {"build_cache_bytes": sum(c.get("Size", 0) for c in cache),
            "build_cache_reclaimable": sum(c.get("Size", 0) for c in cache if not c.get("InUse")),
            "dangling_images": len(dangling), "dangling_bytes": sum(i.get("Size", 0) for i in dangling)}


def foreign_stopped():
    """Stopped containers that belong to other projects: reported so you can decide, never removed here."""
    from engine.supervisor import _docker
    proj = os.environ.get("REGEN_COMPOSE_PROJECT", "deploy")
    rows = _docker("GET", "/containers/json?all=1&filters=" + quote(json.dumps({"status": ["exited", "dead", "created"]}))) or []
    return [r["Names"][0].lstrip("/") for r in rows
            if (r.get("Labels") or {}).get("com.docker.compose.project") != proj]


def bloated():
    """Idle appliers (heartbeat "watching") using more than APPLIER_MB: their browser has grown; a fresh one is
    cheaper. From the supervisor's last inventory (workspace/containers.json) and the fleet heartbeats."""
    from engine.supervisor import containers, fleet
    snap = containers() or {}
    idle = {m["host"] for m in fleet()["members"] if m.get("role") == "applier" and m.get("state") == "watching"}
    return [c for c in snap.get("containers", []) if c.get("service") == "applier" and c.get("id") in idle
            and (c.get("mem_mb") or 0) > APPLIER_MB]


# ---------------- inspection + oil life ----------------
def inspect(st=None, slow=None):
    """Measure every contaminant and the oil life. slow=None: refresh Docker + mail only if older than SLOW_EVERY."""
    from engine import clean
    st = st or load()
    now = time.time()
    files, dirs = clean.plan()
    ws = sum(clean.size(p) for p in files + dirs)
    q = _queue()
    c = dict(st.get("contaminants") or {})
    c.update({"workspace_files": len(files) + len(dirs), "workspace_mb": round(ws / 1e6, 1),
              "queue": len(q), "stale_queue": len(stale_queue(q))})
    if slow or (slow is None and now - (st.get("slow_ts") or 0) > SLOW_EVERY):
        if _docker_ok():
            try:
                d = docker_df()
                c.update(build_cache_gb=round(d["build_cache_reclaimable"] / 1e9, 2),
                         build_cache_total_gb=round(d["build_cache_bytes"] / 1e9, 2),
                         dangling_images=d["dangling_images"], dangling_mb=round(d["dangling_bytes"] / 1e6))
                c["foreign_stopped"] = foreign_stopped()
                c["bloated"] = [{"name": b["name"], "mem_mb": b.get("mem_mb")} for b in bloated()]
            except Exception as ex:
                c["docker_error"] = str(ex)[:120]
        try:
            mb = mail(move=False)
            c["mail"] = mb
            if "skipped" in mb:
                c.pop("old_mail", None)  # no mailbox: it is not part of the oil life
            else:
                c["old_mail"] = sum(v for k, v in mb.items() if isinstance(v, int))
        except Exception as ex:
            c["mail"] = {"error": str(ex)[:120]}
        st["slow_ts"] = now
    st["contaminants"] = c
    st["life"], st["wear"] = life(st, now)
    last = st.get("last_change") or 0
    st["next_due"] = (last + INTERVAL_H * 3600) if last else now
    st["inspected"] = now
    return st


def life(st, now=None):
    """(oil life 0-100, {part: percent used}). Wear grows linearly to 100 over INTERVAL_H since the last change."""
    now = now or time.time()
    c = st.get("contaminants") or {}
    last = st.get("last_change")
    wear = {"age": 100.0 if not last else min(100.0, 100 * (now - last) / (INTERVAL_H * 3600))}
    for k in ("workspace_mb", "build_cache_gb", "old_mail", "stale_queue"):
        if isinstance(c.get(k), (int, float)):
            wear[k] = min(100.0, 100 * c[k] / LIMITS[k])
    if c.get("bloated"):
        wear["applier_mb"] = 100.0
    wear = {k: round(v, 1) for k, v in wear.items()}
    return round(max(0.0, 100 - max(wear.values())), 1), wear


def due(st, now=None):
    if os.path.exists(REQUEST):
        return True  # you asked: always
    if st.get("life") is None or st["life"] > CHANGE_AT:
        return False
    # 10-28: a change that could not lift oil life above CHANGE_AT re-ran every 5 minutes (12 times in an hour).
    # After such a change, the schedule waits one service interval; asking still works.
    last = (st.get("history") or [None])[0]
    after = next((s.get("life_after") for s in (last or {}).get("stages", []) if s.get("name") == "check"), None)
    now = now or time.time()
    return not (last and after is not None and after <= CHANGE_AT and now - (last.get("finished") or last["started"]) < INTERVAL_H * 3600)


# ---------------- the change ----------------
def change(dry=False, by="supervisor"):
    """Run the five stages, saving state after each one so /oilchange animates them live. Returns the run record."""
    from engine import clean
    st = load()
    run = {"started": time.time(), "by": by, "dry": dry, "stages": []}
    st.update(running=True, stage=None, run=run)
    save(st)

    def stage(name, fn):
        st["stage"] = name
        save(st)
        t = time.time()
        try:
            res = fn()
        except Exception as ex:
            res = {"error": str(ex)[:160]}
        run["stages"].append({"name": name, "secs": round(time.time() - t, 1), **res})
        save(st)
        if not dry:
            time.sleep(1.5)  # the page shows every stage at least once, even a fast one

    def drain():
        files, dirs = clean.plan()
        freed = sum(clean.size(p) for p in files + dirs)
        if not dry:
            import shutil
            for f in files:
                try:
                    os.remove(f)
                except OSError:
                    pass
            for d in dirs:
                shutil.rmtree(d, ignore_errors=True)
        shrunk, saved = clean.shrink_proofs() if not dry else (0, 0)
        return {"removed": len(files) + len(dirs), "freed_mb": round((freed + saved) / 1e6, 1), "proofs_shrunk": shrunk}

    def filt():
        mb = mail(move=not dry)
        moved = sum(v for k, v in mb.items() if k.endswith("_moved"))
        return {"mail": mb, "removed": moved if not dry else sum(v for v in mb.values() if isinstance(v, int))}

    def flush():
        if not _docker_ok():
            return {"skipped": "no Docker socket (run inside the supervisor)"}
        from engine.supervisor import _docker, audit, drain_path, FLEET
        out = {"removed": 0, "freed_mb": 0}
        before = docker_df()
        if not dry:
            r = _docker("POST", "/images/prune?filters=" + quote(json.dumps({"dangling": ["true"]}))) or {}
            out["images"] = len(r.get("ImagesDeleted") or [])
            # 10-28: the "until: 72h" filter freed 0 B on Docker Desktop (API and CLI alike) while 10 GB piled up and
            # oil life sat at 0. BuildKit's own budget works: least-recently-used cache goes first down to
            # CACHE_KEEP_GB, so the newest builds stay warm
            r = _docker("POST", f"/build/prune?keep-storage={int(CACHE_KEEP_GB * 1e9)}") or {}
            out["cache_records"] = len(r.get("CachesDeleted") or [])
            out["freed_mb"] = round(((r.get("SpaceReclaimed") or 0)) / 1e6)
            for b in bloated():
                os.makedirs(FLEET, exist_ok=True)
                open(drain_path(b["id"]), "w").write(str(time.time()))  # scale() retires it after the handshake
                audit("drain", b["name"], reason=f"oil change: {b.get('mem_mb')} MB idle")
                out["appliers_drained"] = out.get("appliers_drained", 0) + 1
            after = docker_df()
            out["freed_mb"] = round((before["build_cache_bytes"] + before["dangling_bytes"] - after["build_cache_bytes"]
                                     - after["dangling_bytes"]) / 1e6)
        else:
            out["freed_mb"] = round((before["build_cache_reclaimable"] + before["dangling_bytes"]) / 1e6)
        out["removed"] = out.get("images", 0) + out.get("cache_records", 0) + out.get("appliers_drained", 0)
        out["left_alone"] = foreign_stopped()
        return out

    def refill():
        q = _queue()
        stale = {id(j) for j in stale_queue(q)}
        keep = [j for j in q if id(j) not in stale]
        if not dry and len(keep) != len(q):
            tmp = os.path.join(WORKSPACE, "queue.json.tmp")
            json.dump(keep, open(tmp, "w", encoding="utf-8"), indent=1)
            os.replace(tmp, os.path.join(WORKSPACE, "queue.json"))
        return {"removed": len(q) - len(keep), "queue": len(keep)}

    def check():
        before = (st.get("life"), dict(st.get("wear") or {}))
        if not dry:
            st["last_change"] = time.time()
        inspect(st, slow=True)
        return {"life_before": before[0], "life_after": st["life"]}

    for name, fn in zip(STAGES, (drain, filt, flush, refill, check)):
        stage(name, fn)
    run["finished"] = time.time()
    run["freed_mb"] = round(sum(s.get("freed_mb", 0) or 0 for s in run["stages"]), 1)
    run["removed"] = sum(s.get("removed", 0) or 0 for s in run["stages"])
    st.update(running=False, stage=None)
    if not dry:
        st["history"] = ([run] + (st.get("history") or []))[:20]
    try:
        os.remove(REQUEST)
    except OSError:
        pass
    save(st)
    try:
        from engine.feedback.events import record
        record("oilchange", dry=dry, by=by, removed=run["removed"], freed_mb=run["freed_mb"],
               life_after=st.get("life"), stages=[{k: v for k, v in s.items() if k != "left_alone"} for s in run["stages"]])
    except Exception:
        pass
    return run


_lock = threading.Lock()


def tick_async():
    """The supervisor's 15 s loop calls this: tick() runs in a thread (a change takes up to a minute), one at a time."""
    if _lock.locked():
        return
    def go():
        with _lock:
            tick()
    threading.Thread(target=go, daemon=True).start()


def tick(now=None, _last={}):  # _last: when this supervisor last inspected (kept across calls)
    """Inspect every 5 minutes, change when due. Never raises."""
    now = now or time.time()
    if not os.path.exists(REQUEST) and now - _last.get("t", 0) < 300:
        return None
    _last["t"] = now
    try:
        st = inspect()
        save(st)
        if due(st, now):
            by = "request" if os.path.exists(REQUEST) else "schedule"
            try:
                by = open(REQUEST, encoding="utf-8").read().strip()[:40] or by
            except OSError:
                pass
            return change(by=by)
    except Exception as ex:
        print(f"oilchange: {ex}", flush=True)
    return None


def request(by="operator"):
    """Ask the supervisor for a change now (it picks the request up within 15 s)."""
    with open(REQUEST, "w", encoding="utf-8") as f:
        f.write(by)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--now" in argv:
        if _docker_ok():
            print(json.dumps(change(by="cli"), default=str, indent=1))
        else:
            request("cli")
            print("oilchange: requested; the supervisor starts it within 15 s (watch /oilchange)")
        return
    if "--dry" in argv:
        print(json.dumps(change(dry=True, by="cli"), default=str, indent=1))
        return
    st = inspect(load(), slow="--slow" in argv)
    print(f"oil life {st['life']}% | wear {st['wear']} | last change "
          + (datetime.datetime.fromtimestamp(st['last_change']).isoformat(timespec='minutes') if st.get('last_change') else "never"))


if __name__ == "__main__":
    main()
