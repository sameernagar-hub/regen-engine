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


def test_live_view_rejects_rebound_host():
    from engine.live import server
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    def get(host):
        req = urllib.request.Request(f"http://127.0.0.1:{port}/", headers={"Host": host})
        try:
            return urllib.request.urlopen(req, timeout=5).status
        except urllib.error.HTTPError as e:
            return e.code
    try:
        assert get(f"127.0.0.1:{port}") == 200
        assert get("evil.example") == 403
    finally:
        srv.shutdown()


def test_scale_never_retires_the_last_applier(tmp_path, monkeypatch):
    """10-17: the only applier carried a drain, confirmed it, and was deleted; with none left to clone from, the
    supervisor could never create another. Below the minimum the drain is cancelled instead."""
    import os
    from engine import supervisor as S
    for k, v in (("FLEET", tmp_path / "fleet"), ("BOX", tmp_path / "batches"), ("WORKSPACE", tmp_path)):
        monkeypatch.setattr(S, k, str(v))
    for d in ("inbox", "claimed"):
        os.makedirs(tmp_path / "batches" / d)
    os.makedirs(tmp_path / "fleet")
    # the drained one + a container compose is replacing (running, no heartbeat): active == want, so no cancel branch
    rows = [("c" * 64, "deploy-applier-3", True), ("d" * 64, "deploy-applier-4", True)]
    calls, acts = [], []
    monkeypatch.setattr(S, "appliers", lambda: rows)
    monkeypatch.setattr(S, "_docker", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(S, "audit", lambda action, target, **kw: acts.append((action, target)))
    open(S.drain_path("c" * 12), "w").write("1")
    (tmp_path / "fleet" / f"applier_{'c' * 12}.json").write_text(
        json.dumps({"role": "applier", "host": "c" * 12, "state": "draining", "ts": __import__("time").time()}))
    monkeypatch.setattr(S, "clone", lambda *a: calls.append("clone"))
    S.scale(1, 7, _idle={})
    assert not any(c[0] in ("POST", "DELETE") for c in calls if isinstance(c, tuple))
    assert not os.path.exists(S.drain_path("c" * 12)) and ("keep", "deploy-applier-3") in acts
    # 10-19: gear N asks for 0-0 appliers; the last one still stays (else shifting back up could create nothing)
    calls.clear(); acts.clear()
    open(S.drain_path("c" * 12), "w").write("1")
    S.scale(0, 0, _idle={})
    assert not any(c[0] in ("POST", "DELETE") for c in calls if isinstance(c, tuple)) and ("keep", "deploy-applier-3") in acts


def test_clean_drops_dead_heartbeats_only(tmp_path, monkeypatch):
    import os, time
    from engine import clean as C
    monkeypatch.setattr(C, "WORKSPACE", str(tmp_path))
    (tmp_path / "fleet").mkdir()
    dead, live, marker = (tmp_path / "fleet" / n for n in ("applier_aaaa.json", "applier_bbbb.json", "daily_last"))
    for f in (dead, live, marker):
        f.write_text("{}")
    for f in (dead, marker):
        os.utime(f, (time.time() - 2 * 86400,) * 2)
    files, _ = C.plan()
    assert [os.path.basename(f) for f in files] == ["applier_aaaa.json"]
