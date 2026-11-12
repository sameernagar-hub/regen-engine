"""The discovery scout (11-11): new boards from public APIs, new feeds from GitHub lists, names probed once."""
import json

import pytest

from engine.discovery import ats as A, scout as S


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "STATE", str(tmp_path / "scout.json"))
    monkeypatch.setattr(S, "WORKSPACE", str(tmp_path))
    monkeypatch.setattr(A, "boards_path", lambda: str(tmp_path / "boards.json"))
    monkeypatch.setattr(S, "record", lambda *a, **k: None)
    A.save_boards({a: [] for a in A.ATS} | {"greenhouse": ["knownco"]})
    return tmp_path


def test_api_apply_links_add_only_new_boards(ws, monkeypatch):
    rows = [{"company_name": "Acme", "url": "https://job-boards.greenhouse.io/acme/jobs/123"},
            {"company_name": "Known", "url": "https://boards.greenhouse.io/knownco/jobs/9"},
            {"company_name": "Plain", "url": "https://example.com/careers/1"}]
    monkeypatch.setattr(S, "_get", lambda url, timeout=30: json.dumps({"jobs": rows}))
    s = S._load()
    monkeypatch.setattr(S, "APIS", {"fake": ("https://x", "jobs", "company_name", ("url",))})
    out, names = S.apis(s)
    assert out["fake"] == {"jobs": 3, "boards_added": 1}
    assert "acme" in A.load_boards()["greenhouse"]
    assert set(names) == {"Acme", "Known", "Plain"}
    assert s["sources"]["fake"]["boards_added"] == 1


def test_a_failing_api_is_tallied_not_raised(ws, monkeypatch):
    def boom(url, timeout=30):
        raise OSError("down")
    monkeypatch.setattr(S, "_get", boom)
    monkeypatch.setattr(S, "APIS", {"fake": ("https://x", "jobs", "company_name", ("url",))})
    s = S._load()
    out, names = S.apis(s)
    assert out["fake"] == {"error": "OSError"} and names == []
    assert s["sources"]["fake"]["errors"] == 1


def test_names_are_probed_once(ws, monkeypatch):
    calls = []
    import engine.discovery.sources as src
    monkeypatch.setattr(src, "probe_companies", lambda ns, by="": calls.append(list(ns)) or {"found": [["ashby", "acme"]]})
    s = S._load()
    assert S.names(s, ["Acme", "acme", "Beta"])["probed"] == 2
    assert S.names(s, ["ACME", "Beta", "Gamma"])["probed"] == 1
    assert calls == [["Acme", "Beta"], ["Gamma"]]


def test_a_readme_becomes_a_feed_only_with_enough_boards(ws, monkeypatch):
    import engine.discovery.sources as src
    added = []
    monkeypatch.setattr(src, "feeds", lambda: [])
    monkeypatch.setattr(src, "add_feed", lambda url, by="": added.append(url) or {"boards_added": 20})
    monkeypatch.setattr(S.time, "sleep", lambda s: None)
    monkeypatch.setattr(S, "QUERIES", ["q"])
    rich = " ".join(f"https://job-boards.greenhouse.io/co{i}/jobs/1" for i in range(S.MIN_LINKS))

    def get(url, timeout=30):
        if "api.github.com" in url:
            return json.dumps({"items": [{"full_name": "a/rich", "default_branch": "main"},
                                         {"full_name": "b/thin", "default_branch": "main"}]})
        return rich if "a/rich" in url else "https://job-boards.greenhouse.io/one/jobs/1"
    monkeypatch.setattr(S, "_get", get)
    s = S._load()
    assert S.lists(s) == {"repos": 2, "boards_added": 20}
    assert added == ["https://raw.githubusercontent.com/a/rich/main/README.md"]
    assert S.lists(s)["repos"] == 0  # both repos remembered: never fetched again


def test_a_round_runs_without_the_optional_profile_file(ws, monkeypatch, tmp_path):
    """11-11: profile_file() exited on the missing optional profile/scout.json and the container crash-looped."""
    import engine.config as C
    monkeypatch.setattr(C, "PROFILE", str(tmp_path / "no-profile"))
    monkeypatch.setattr(S, "lists", lambda s: {"repos": 0, "boards_added": 0})
    monkeypatch.setattr(S, "apis", lambda s, extra=None: ({}, []))
    monkeypatch.setattr(S, "names", lambda s, c: {"probed": 0, "boards_added": 0})
    r = S.round_once()
    assert r["boards_after"] == r["boards_before"]
