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
