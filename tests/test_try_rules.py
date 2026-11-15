"""The web quick start (apps/web/lib/try-rules.json) must carry the same rules as `python -m engine try`."""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import try_rules  # noqa: E402


def test_try_rules_json_is_current():
    have = open(try_rules.OUT, encoding="utf-8").read()
    assert have == try_rules.text(), "apps/web/lib/try-rules.json is stale: run python scripts/try_rules.py"
