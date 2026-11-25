"""Claude cord (engine/cord.py): agents ask, Claude replies, one open ask per key, questions save as Shadow."""
import engine.cord as C


def paths(tmp_path):
    return {"asks_path": str(tmp_path / "a.jsonl"), "replies_path": str(tmp_path / "r.jsonl")}


def test_ask_dedupes_by_key_while_open(tmp_path):
    p = paths(tmp_path)
    a = C.ask("shadow", "Years of Go?", key="q:go", context={"job": "Acme - SWE", "question": "Years of Go?"}, now=100, **p)
    b = C.ask("shadow", "Years of Go?", key="q:go", now=200, **p)
    assert a == b and len(C.open_asks(now=300, **p)) == 1


def test_reply_saves_question_as_shadow_and_closes(tmp_path):
    p, saved = paths(tmp_path), []
    aid = C.ask("shadow", "Notice period?", context={"job": "Acme - SWE", "question": "Notice period?"}, now=100, **p)
    out = C.reply(aid, "2 weeks", save=lambda *a, **k: saved.append((a, k)) or {"ok": True}, **p)
    assert out["saved"] == {"ok": True} and saved[0][1]["by"] == "shadow"
    assert C.open_asks(now=150, **p) == []
    assert "error" in C.reply(aid, "again", save=lambda *a, **k: None, **p)  # one reply per ask


def test_refused_answer_keeps_ask_open(tmp_path):
    p = paths(tmp_path)
    aid = C.ask("shadow", "Gender?", context={"job": "Acme - SWE", "question": "Gender?"}, now=100, **p)

    def refuse(*a, **k):
        raise ValueError("EEO is decline-only")
    assert "refused" in C.reply(aid, "Male", save=refuse, **p)["error"]
    assert len(C.open_asks(now=150, **p)) == 1


def test_problem_reply_has_no_save(tmp_path):
    p = paths(tmp_path)
    aid = C.ask("supervisor", "no applier is alive", kind="problem", now=100, **p)
    out = C.reply(aid, "recreated applier", save=lambda *a, **k: 1 / 0, **p)
    assert "saved" not in out and out["by"] == "claude"


def test_ignite_refuses_overdrive():
    from engine.ignite import ignite
    assert "refused" in ignite(gear="4")["error"]


# ---- 11-24 ignition request route (engine/ignite.py): the API drops a request, the supervisor runs it ----
import json, os
import engine.ignite as I


def test_ignite_request_refuses_gear_4_and_bad_values(tmp_path):
    p = str(tmp_path / "req.json")
    for bad in ({"gear": "4"}, {"keywords": "maybe"}, {"cap": 9}, {"shadow": "loud"}):
        try:
            I.request(**bad, path=p)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass
    assert not os.path.exists(p)
    I.request("2", "off", 1, "calls", path=p)
    assert json.load(open(p))["gear"] == "2"


def test_apply_request_runs_once_and_consumes_the_file(tmp_path, monkeypatch):
    p, started = str(tmp_path / "req.json"), []

    class Fake:
        def __init__(self, argv, **kw):
            started.append(argv)

        def poll(self):
            return 0
    monkeypatch.setattr(I.subprocess, "Popen", Fake)
    monkeypatch.setattr(I, "_CHILD", None)
    assert I.apply_request(path=p) is False  # nothing pending
    I.request("3", "on", 4, "autopilot", path=p)
    assert I.apply_request(path=p) is True and not os.path.exists(p)
    argv = started[0]
    assert argv[argv.index("--gear") + 1] == "3" and argv[argv.index("--cap") + 1] == "4"
    assert I.apply_request(path=p) is False and len(started) == 1


def test_status_reads_last_and_pending(tmp_path):
    last, req = str(tmp_path / "last.json"), str(tmp_path / "req.json")
    json.dump({"t": 1, "by": "mcp", "result": {"gear": "drive"}}, open(last, "w"))
    s = I.status(last_path=last, request_path=req)
    assert s["last"]["by"] == "mcp" and s["pending"] is False and "agents" in s
