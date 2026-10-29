"""Tests run against profile.example/, a fictional persona (tests/fixtures/presets.json) and a throwaway workspace,
never your real profile or history."""
import os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["REGEN_PROFILE"] = os.path.join(ROOT, "profile.example")
os.environ["REGEN_WORKSPACE"] = tempfile.mkdtemp(prefix="regen-test-")
os.environ["REGEN_PRESETS"] = os.path.join(ROOT, "tests", "fixtures", "presets.json")  # fictional "Jane Doe"
os.environ.pop("REGEN_FACTS", None)
# never the real mailbox: engine/notify.py's _env() reads the repo's .env only for keys not already set (10-27: an oil
# change test moved real mail to Bin)
for k in ("REGEN_SMTP_USER", "REGEN_SMTP_APP_PASSWORD"):
    os.environ[k] = ""
