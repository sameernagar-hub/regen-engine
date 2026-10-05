"""Tests run against profile.example/ and a throwaway workspace, never your real profile or history."""
import os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["REGEN_PROFILE"] = os.path.join(ROOT, "profile.example")
os.environ["REGEN_WORKSPACE"] = tempfile.mkdtemp(prefix="regen-test-")
os.environ.pop("REGEN_PRESETS", None)
os.environ.pop("REGEN_FACTS", None)
