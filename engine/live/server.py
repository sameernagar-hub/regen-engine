"""`python -m engine live [port=7777]`: the engine, watched live. Not a dashboard.

A tiny standard-library server, bound to 127.0.0.1 only and strictly read-only, that tails workspace/events.jsonl
and streams every event to the page as one plain-English sentence (Server-Sent Events). The page (index.html,
no build step, no CDN, no tracking) draws the work as it happens:
listening -> judging -> writing -> applying -> hearing back.

  GET /         the page
  GET /stream   SSE: a snapshot ("state"), a short replay of recent events, then every new event as it lands
"""
import json, os, re, sys, time, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from engine.config import WORKSPACE

HERE = os.path.dirname(os.path.abspath(__file__))
EVENTS = lambda: os.path.join(WORKSPACE, "events.jsonl")


def short(s, n=70):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def who(job):
    """'Nuro - New Grad Software Engineer, Routing' -> ('Nuro', 'New Grad Software Engineer, Routing')"""
    co, _, role = (job or "").partition(" - ")
    return co.strip(), short(role.strip(), 60)


def narrate(e):
    """One event -> {stage, tone, text}. Plain words, no jargon, nothing invented. None = not worth showing."""
    k, st = e.get("kind"), (e.get("status") or "")
    co, role = who(e.get("job"))
    if k == "discovered":
        lag = e.get("lag_min")
        return dict(stage="listen", tone="calm",
                    text=f"Spotted {co}: {role}" + (f", {lag} min after it went live." if lag is not None else "."))
    if k == "resume":
        n = sum(len(f) for _, f in e.get("facts") or [])
        return dict(stage="write", tone="calm",
                    text=f"Wrote a resume for {co}" + (f" from {n} facts in your Fact Bank" if n else "")
                         + (f", {e['lane']} lane." if e.get("lane") else "."))
    if k == "application":
        if e.get("dry"):
            return None
        d = e.get("detail") or ""
        if st == "SKIPPED":
            return dict(stage="judge", tone="quiet", text=f"Let {co} go: {short(d.replace('JD: ', ''), 60)}.")
        if st == "SUBMITTED":
            proof = e.get("proof") and os.path.exists(os.path.join(WORKSPACE, e["proof"]))
            return dict(stage="apply", tone="win", text=f"Applied to {co}, {role}." + (" Proof saved." if proof else ""), verified=bool(proof))
        if e.get("correction"):
            return dict(stage="apply", tone="alarm", text=f"Corrected the record for {co}: {short(d, 80)}")
        if st.startswith("FLAG"):
            return dict(stage="apply", tone="alarm", text=f"Stopped before submitting {co}: {short(d, 80)}")
        if st == "NEEDS YOU" or "BOT-CHECK" in d:
            why = "Ashby wants a human click" if "BOT-CHECK" in d or "cooldown" in d else short(re.sub(r"^(NEEDS YOU|FAILED):\s*", "", d), 60)
            return dict(stage="apply", tone="you", text=f"{co} needs you: {why}.")
        return dict(stage="apply", tone="quiet", text=f"{co} didn't go through yet: {short(d.split(':', 1)[-1], 60)}.")
    if k == "flag":
        return dict(stage="apply", tone="alarm", text=f"Airbag: stopped {co}. {short(e.get('detail'), 80)}")
    if k == "outcome":
        c, o = e.get("company") or "Someone", e.get("outcome")
        text = {"confirmation": f"{c} confirmed they have your application.",
                "interview": f"{c} wants to talk to you.",
                "oa": f"{c} sent an assessment.",
                "offer": f"{c} made an offer.",
                "rejection": f"{c} passed this time.",
                "action": f"{c} is asking for something.",
                "scam": f"Something from {c} looks like a scam. Ignored and flagged."}.get(o)
        tone = {"interview": "win", "oa": "win", "offer": "win", "scam": "alarm", "action": "you"}.get(o, "calm")
        return dict(stage="hear", tone=tone, text=text) if text else None
    return None


def snapshot():
    """Numbers the page shows, all derived from evidence on disk."""
    latest, waiting, lanes = {}, 0, {}
    if os.path.exists(EVENTS()):
        for line in open(EVENTS(), encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("kind") == "resume" and e.get("lane"):
                lanes[e.get("job")] = e["lane"]                  # which resume lane wrote this application
            if e.get("kind") == "application" and not e.get("dry"):
                latest[" ".join((e.get("job") or "").lower().split())] = e  # by job name: old backfilled events have no url
    verified = [e for e in latest.values() if e.get("status") == "SUBMITTED" and e.get("proof")
                and os.path.exists(os.path.join(WORKSPACE, e["proof"]))]
    waiting_items = []
    for e in latest.values():  # what is waiting on the human NOW (each job's latest status), not old history
        if e.get("status") in ("NEEDS YOU", "FAILED", "FLAGGED"):  # not submitted, not deliberately skipped
            n = narrate(dict(e, status=e["status"] if e["status"] != "FAILED" else "NEEDS YOU"))
            if n:
                waiting_items.append(n["text"])
    waiting = len(waiting_items)
    boards = 0
    try:
        b = json.load(open(os.path.join(WORKSPACE, "boards.json")))
        boards = sum(len(v) for k, v in b.items() if k != "dead") - len(b.get("dead", []))
    except (OSError, ValueError):
        pass
    seen = os.path.join(WORKSPACE, "seen.json")
    last_poll = os.path.getmtime(seen) if os.path.exists(seen) else None
    today = time.strftime("%Y-%m-%d")
    return dict(verified=len(verified), verified_jobs=[list(who(e["job"])) + [lanes.get(e["job"]) or "earlier"] for e in sorted(verified, key=lambda e: e["ts"])],
                verified_today=sum(1 for e in verified if e["ts"].startswith(today)),
                waiting=waiting, waiting_items=waiting_items[-12:], boards=boards, last_poll=last_poll)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = open(os.path.join(HERE, "index.html"), "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")
            self.end_headers(); self.wfile.write(body); return
        if self.path == "/stream":
            return self.stream()
        self.send_response(404); self.end_headers()

    def send(self, kind, data):
        self.wfile.write(f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
        self.wfile.flush()

    def stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            self.send("state", snapshot())
            pos, recent = 0, []
            if os.path.exists(EVENTS()):
                with open(EVENTS(), encoding="utf-8") as fh:
                    for line in fh:
                        recent.append(line)
                    pos = fh.tell()
            for line in recent[-40:]:  # a short replay so the page opens already alive
                m = self._msg(line)
                if m:
                    self.send("event", dict(m, replay=True))
            last_state = time.time()
            while True:
                time.sleep(1)
                if os.path.exists(EVENTS()) and os.path.getsize(EVENTS()) > pos:
                    with open(EVENTS(), encoding="utf-8") as fh:
                        fh.seek(pos)
                        for line in fh:
                            m = self._msg(line)
                            if m:
                                self.send("event", m)
                        pos = fh.tell()
                    self.send("state", snapshot()); last_state = time.time()
                elif time.time() - last_state > 15:
                    self.send("state", snapshot()); last_state = time.time()  # also a keep-alive
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    @staticmethod
    def _msg(line):
        try:
            e = json.loads(line)
        except ValueError:
            return None
        n = narrate(e)
        return dict(n, ts=e.get("ts")) if n else None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    port = int(argv[0]) if argv and argv[0].isdigit() else 7777
    # localhost only by default. In Docker the container binds 0.0.0.0 but compose publishes it on 127.0.0.1 only.
    host = os.environ.get("REGEN_LIVE_HOST", "127.0.0.1")
    srv = ThreadingHTTPServer((host, port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"live view: {url}  (read-only; Ctrl+C to stop)", flush=True)
    if "--no-open" not in argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
