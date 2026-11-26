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


def test_cord_files_are_handed_to_the_engine_user_when_root_writes_them(tmp_path, monkeypatch):
    """11-25: the supervisor (root) created /data/workspace/cord, so cord_reply (uid 10001) could not write a reply."""
    import os
    chowned = []
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(os, "chown", lambda p, u, g: chowned.append((str(p), u, g)), raising=False)
    asks = tmp_path / "cord" / "asks.jsonl"
    C.ask("supervisor", "x", asks_path=str(asks), replies_path=str(tmp_path / "cord" / "replies.jsonl"))
    assert (str(tmp_path / "cord"), 10001, 10001) in chowned
    assert (str(asks), 10001, 10001) in chowned
    if os.sep == "/":
        assert asks.stat().st_mode & 0o666 == 0o666


def test_two_asks_in_the_same_millisecond_get_distinct_ids_and_replies_save_the_right_question(tmp_path):
    """11-25: ids were f"{from}-{ms}", so same-ms asks collided and one reply saved only the first question."""
    p = paths(tmp_path)
    a = C.ask("shadow", "Years of Go?", key="q:go", context={"job": "Acme - SWE", "question": "Years of Go?"}, now=100.0, **p)
    b = C.ask("shadow", "Years of Rust?", key="q:rust", context={"job": "Acme - SWE", "question": "Years of Rust?"}, now=100.0, **p)
    assert a != b and a.startswith("shadow-100000-") and b.startswith("shadow-100000-")
    saved = []
    save = lambda job, q, ans, by: saved.append((job, q, ans)) or {"ok": True}
    assert "error" not in C.reply(b, "1", save=save, **p)
    assert saved == [("Acme - SWE", "Years of Rust?", "1")]
    assert [x["id"] for x in C.open_asks(now=101, **p)] == [a]  # the other ask is still open
    assert "error" not in C.reply(a, "3", save=save, **p)
    assert saved[-1] == ("Acme - SWE", "Years of Go?", "3")
