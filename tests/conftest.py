"""Tests run against profile.example/, a fictional persona (tests/fixtures/presets.json) and a throwaway workspace,
never your real profile or history."""
import os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["REGEN_PROFILE"] = os.path.join(ROOT, "profile.example")
os.environ["REGEN_WORKSPACE"] = tempfile.mkdtemp(prefix="regen-test-")
os.environ["REGEN_PRESETS"] = os.path.join(ROOT, "tests", "fixtures", "presets.json")  # fictional "Jane Doe"
os.environ.pop("REGEN_FACTS", None)
