"""Hands-free email codes without an app password: a signed-in Gmail tab pushes codes to this local relay.

    python -m engine relay [port]        (default 8799, binds 127.0.0.1 only)

The tab runs engine/discovery/gmail_relay.js: every 20 s it reads Gmail's Atom feed (unread inbox, one fetch) and
POSTs [{company, code, iso}] here as text/plain (a "simple" request: no CORS preflight). The relay converts the
send time to local "HH:MM" and calls codes.match(), which writes workspace/codes/<board>_<id>.txt only for a job that
is waiting and whose company matches, and only for codes sent after it started waiting. Nothing else is accepted:
the body must be a JSON list of short {company, code, iso} records, and the server listens on loopback only.
"""
import datetime, html, http.server, json, os, re, sys, threading, time

from engine.apply import codes as C
from engine.supervisor import beat

SEEN = set()
LAST = {"last_post": None, "codes": 0}


class Relay(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20000:
            self.send_response(413); self.end_headers(); return
        try:
            rows = json.loads(self.rfile.read(n) or b"[]")
            assert isinstance(rows, list)
            out = []
            for r in rows[:50]:
                co, code = html.unescape(str(r["company"]))[:80], str(r["code"])  # the Atom feed sends "&amp;"
                if not re.fullmatch(r"[A-Za-z0-9]{6,10}", code):
                    continue
                t = datetime.datetime.fromisoformat(str(r.get("iso", "")).replace("Z", "+00:00")).astimezone()
                out.append({"company": co, "code": code, "when": t.strftime("%H:%M")})
        except (ValueError, KeyError, AssertionError, TypeError):
            self.send_response(400); self.end_headers(); return
        waiting = C.waiting()
        written = C.match(out) if waiting else {}
        for slug, code in (written or {}).items():
            if (slug, code) not in SEEN:
                SEEN.add((slug, code))
                print(f"{datetime.datetime.now():%H:%M:%S} code -> {slug}", flush=True)
                LAST["codes"] += 1
        LAST["last_post"] = time.time()
        beat("relay", state="listening", waiting=len(waiting), **LAST)
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "https://mail.google.com")
        self.end_headers()
        self.wfile.write(json.dumps({"written": sorted(written or {}), "waiting": len(waiting)}).encode())

    def do_GET(self):
        """http://127.0.0.1:8799/ : what the relay is doing (jobs waiting on a code, codes delivered, last post),
        refreshed every 5 s; /status is the same as JSON. Never shows a code value, only which jobs wait."""
        waiting = C.waiting()
        st = {"waiting": [{"job": s, "company": co} for s, co in waiting], "delivered": LAST["codes"],
              "last_post_s_ago": round(time.time() - LAST["last_post"]) if LAST["last_post"] else None}
        if self.path.startswith("/status"):
            body, ctype = json.dumps(st).encode(), "application/json"
        elif self.path in ("/", "/index.html"):
            rows = "".join(f"<tr><td>{html.escape(w['company'])}</td><td>{html.escape(w['job'])}</td></tr>" for w in st["waiting"])
            body = (f"<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=5><title>REGEN code relay</title>"
                    f"<style>body{{background:#0b0f14;color:#e6edf3;font:14px system-ui;padding:16px}}td,th{{padding:4px 10px;"
                    f"border-bottom:1px solid #223041;text-align:left}}.dim{{color:#8b98a8}}a{{color:#6fb7ff}}</style>"
                    f"<h1 style='font-size:16px'>REGEN · code relay 127.0.0.1:8799</h1>"
                    f"<p>{len(st['waiting'])} job(s) waiting on an email code · {st['delivered']} delivered by this relay · "
                    f"last post from the Gmail tab: {str(st['last_post_s_ago']) + ' s ago' if st['last_post_s_ago'] is not None else 'never'}"
                    f"</p><p class=dim>The supervisor's IMAP watcher delivers codes too; this page lists what still waits. "
                    f"Refreshes every 5 s. <a href='/status'>JSON</a> · <a href='http://127.0.0.1:8787/'>API</a> · "
                    f"<a href='http://127.0.0.1:3000/control'>Control room</a></p>"
                    f"<table><tr><th>company</th><th>job (board_id)</th></tr>{rows or '<tr><td class=dim colspan=2>nothing waiting</td></tr>'}</table>").encode()
            ctype = "text/html; charset=utf-8"
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass  # quiet: one line per delivered code is printed above


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    port = int(argv[0]) if argv else 8799
    print(f"code relay on http://127.0.0.1:{port} (POST codes from the Gmail tab)", flush=True)
    host = os.environ.get("REGEN_RELAY_HOST", "127.0.0.1")  # 0.0.0.0 inside a container; compose publishes 127.0.0.1 only
    def idle():
        while True:
            beat("relay", state="listening", **LAST)
            time.sleep(60)
    threading.Thread(target=idle, daemon=True).start()
    http.server.ThreadingHTTPServer((host, port), Relay).serve_forever()


if __name__ == "__main__":
    main()
