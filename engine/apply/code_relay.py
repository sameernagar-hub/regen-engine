"""Hands-free email codes without an app password: a signed-in Gmail tab pushes codes to this local relay.

    python -m engine relay [port]        (default 8799, binds 127.0.0.1 only)

The tab runs engine/discovery/gmail_relay.js: every 20 s it reads Gmail's Atom feed (unread inbox, one fetch) and
POSTs [{company, code, iso}] here as text/plain (a "simple" request: no CORS preflight). The relay converts the
send time to local "HH:MM" and calls codes.match(), which writes workspace/codes/<board>_<id>.txt only for a job that
is waiting and whose company matches, and only for codes sent after it started waiting. Nothing else is accepted:
the body must be a JSON list of short {company, code, iso} records, and the server listens on loopback only.
"""
import datetime, http.server, json, re, sys

from engine.apply import codes as C

SEEN = set()


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
                co, code = str(r["company"])[:80], str(r["code"])
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
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "https://mail.google.com")
        self.end_headers()
        self.wfile.write(json.dumps({"written": sorted(written or {}), "waiting": len(waiting)}).encode())

    def log_message(self, *a):
        pass  # quiet: one line per delivered code is printed above


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    port = int(argv[0]) if argv else 8799
    print(f"code relay on http://127.0.0.1:{port} (POST codes from the Gmail tab)", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Relay).serve_forever()


if __name__ == "__main__":
    main()
