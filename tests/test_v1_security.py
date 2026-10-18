"""v1 release review: the local services refuse pages that are not this machine's own control room."""
import http.server, json, threading, urllib.request, urllib.error

from fastapi.testclient import TestClient

from apps.api import control, main as M
from engine.apply import code_relay


def test_api_rejects_rebound_host():
    """DNS rebinding: a foreign name that resolves to 127.0.0.1 must not read the API (Host header check)."""
    c = TestClient(M.app)
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    assert c.get("/api/health", headers={"Host": "127.0.0.1:8787"}).status_code == 200
    assert c.get("/api/health", headers={"Host": "api:8787"}).status_code == 200


def test_desk_url_carries_this_starts_password(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "WORKSPACE", str(tmp_path))
    assert "password" not in control._desk_url()
    (tmp_path / ".desk_pass").write_text("aB3 x&y\n")
    assert control._desk_url().endswith("&password=aB3%20x%26y")


def _serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), code_relay.Relay)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _post(port, headers):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/", data=b"[]", headers=headers, method="POST")
    try:
        return urllib.request.urlopen(req, timeout=5).status
    except urllib.error.HTTPError as e:
        return e.code


def test_relay_accepts_gmail_and_curl_only(monkeypatch):
    monkeypatch.setattr(code_relay.C, "waiting", lambda *a: [])
    monkeypatch.setattr(code_relay, "beat", lambda *a, **k: None)
    srv, port = _serve()
    try:
        assert _post(port, {}) == 200                                          # curl / IMAP: no Origin
        assert _post(port, {"Origin": "https://mail.google.com"}) == 200        # the Gmail tab
        assert _post(port, {"Origin": "https://evil.example"}) == 403           # any other page
        assert _post(port, {"Host": "evil.example"}) == 403                     # rebinding
    finally:
        srv.shutdown()
