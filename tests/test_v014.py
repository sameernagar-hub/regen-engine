"""v0.14: supervisor guardrails - every container the supervisor creates is bounded, labeled, counted and audited;
undeclared containers are stopped; supervisor-made appliers are recycled after a TTL (offline, faked Docker API)."""
import json, os, re

import pytest

from engine import supervisor as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _body(svc="applier", **hc):
    return {"Image": "regen-applier:local", "Labels": {"com.docker.compose.service": svc}, "HostConfig": hc}


def test_declared_services_match_the_compose_file():
    text = open(os.path.join(ROOT, "deploy", "bank.compose.yml"), encoding="utf-8").read()
    block = text.split("\nservices:", 1)[1].split("\nvolumes:", 1)[0]
    assert set(re.findall(r"^  ([a-z][a-z0-9-]*):", block, re.M)) == S.DECLARED


def test_bound_caps_limits_and_labels():
    b = S.bound(_body(NanoCpus=4_000_000_000, Memory=0, Binds=["regen-workspace:/app/workspace"], CapAdd=["SYS_ADMIN"],
                      Privileged=True), existing=2)
    hc, cap = b["HostConfig"], S.CAPS["applier"]
    assert hc["NanoCpus"] == cap["NanoCpus"] and hc["Memory"] == cap["Memory"] and hc["PidsLimit"] == cap["PidsLimit"]
    assert hc["Privileged"] is False and "CapAdd" not in hc
    assert b["Labels"][S.MANAGED] == "supervisor" and b["Labels"]["regen.created"].isdigit()
    small = S.bound(_body(NanoCpus=500_000_000, Memory=2 ** 28), existing=0)["HostConfig"]
    assert small["NanoCpus"] == 500_000_000 and small["Memory"] == 2 ** 28  # below the cap: kept


@pytest.mark.parametrize("body,existing,why", [
    (_body("pipeline"), 0, "not scalable"),
    (_body(), S.HARD_MAX, "hard max"),
    (_body(Binds=["/var/run/docker.sock:/var/run/docker.sock"]), 0, "Docker socket"),
    (_body(Mounts=[{"Source": "/var/run/docker.sock"}]), 0, "Docker socket"),
])
def test_bound_refuses(body, existing, why):
    with pytest.raises(S.Refused, match=why):
        S.bound(body, existing)


def test_scale_audits_a_refused_create(tmp_path, monkeypatch):
    for k, v in (("FLEET", tmp_path / "fleet"), ("BOX", tmp_path / "batches"), ("WORKSPACE", tmp_path)):
        monkeypatch.setattr(S, k, str(v))
    for d in ("inbox", "claimed"):
        os.makedirs(tmp_path / "batches" / d)
    (tmp_path / "batches" / "inbox" / "x.json").write_text(json.dumps([{}] * 9))  # 9 jobs -> want 3
    monkeypatch.setattr(S, "appliers", lambda: [("a" * 64, "deploy-applier-1", True)])
    monkeypatch.setattr(S, "_docker", lambda *a, **k: None)
    acts = []
    monkeypatch.setattr(S, "audit", lambda action, target, **kw: acts.append((action, kw.get("reason", ""))))

    def refuse(*a):
        raise S.Refused("hard max")
    monkeypatch.setattr(S, "clone", refuse)
    S.scale(1, 7, _idle={})
    assert acts == [("refuse", "hard max")]  # once per pass, not once per missing container


def test_enforce_stops_undeclared_bounds_unlimited_and_expires_old(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "FLEET", str(tmp_path / "fleet"))
    now = 1_000_000.0
    rows = [
        {"Id": "f" * 64, "Names": ["/deploy-miner-1"], "State": "running", "Labels": {"com.docker.compose.service": "miner"}},
        {"Id": "a" * 64, "Names": ["/deploy-applier-1"], "State": "running",
         "Labels": {"com.docker.compose.service": "applier"}},
        {"Id": "b" * 64, "Names": ["/deploy-applier-2"], "State": "running",
         "Labels": {"com.docker.compose.service": "applier", S.MANAGED: "supervisor", "regen.created": str(int(now - S.TTL - 60))}},
        {"Id": "c" * 64, "Names": ["/deploy-api-1"], "State": "running", "Labels": {"com.docker.compose.service": "api"}},
    ]
    calls = []

    def docker(m, path, body=None):
        calls.append((m, path, body))
        if path.startswith("/containers/json"):
            return rows
        if path.endswith("/json"):
            cid = path.split("/")[2]
            return {"HostConfig": {} if cid.startswith("a") else dict(S.CAPS["applier"])}
    monkeypatch.setattr(S, "_docker", docker)
    acts = []
    monkeypatch.setattr(S, "audit", lambda action, target, **kw: acts.append((action, target)))
    out = S.enforce(now)
    assert out == [("stop", "deploy-miner-1"), ("bound", "deploy-applier-1"), ("expire", "deploy-applier-2")]
    assert ("POST", "/containers/" + "f" * 64 + "/stop?t=10", None) in calls
    upd = [c for c in calls if c[1].endswith("/update")]
    assert len(upd) == 1 and upd[0][2] == S.CAPS["applier"]
    assert S._expired("b" * 64) and not S._expired("a" * 64)
    assert S.enforce(now)[-1] == ("bound", "deploy-applier-1")  # the drain exists: not expired (or audited) twice


def test_expired_drain_is_never_cancelled(tmp_path, monkeypatch):
    for k, v in (("FLEET", tmp_path / "fleet"), ("BOX", tmp_path / "batches"), ("WORKSPACE", tmp_path)):
        monkeypatch.setattr(S, k, str(v))
    for d in ("inbox", "claimed"):
        os.makedirs(tmp_path / "batches" / d)
    os.makedirs(tmp_path / "fleet")
    rows = [("a" * 64, "deploy-applier-1", True), ("b" * 64, "deploy-applier-2", True)]
    monkeypatch.setattr(S, "appliers", lambda: rows)
    monkeypatch.setattr(S, "_docker", lambda *a, **k: None)
    made = []
    monkeypatch.setattr(S, "clone", lambda *a: made.append(1) or "deploy-applier-3")
    monkeypatch.setattr(S, "audit", lambda *a, **k: None)
    open(S.drain_path("b" * 12), "w").write("expire 1")
    (tmp_path / "batches" / "inbox" / "x.json").write_text(json.dumps([{}] * 6))  # want 2
    S.scale(1, 7, _idle={})
    assert os.path.exists(S.drain_path("b" * 12)) and made == [1]  # a fresh one replaces it instead
