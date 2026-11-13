"""Paths shared by every stage.

ROOT       repo root
PROFILE    your private profile (fact_bank.json, presets.json). Git-ignored. Override: REGEN_PROFILE
WORKSPACE  runtime state: queue, resumes, proof screenshots, logs, browser profile. Git-ignored. Override: REGEN_WORKSPACE
"""
import os
from contextlib import contextmanager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE = os.environ.get("REGEN_PROFILE", os.path.join(ROOT, "profile"))
WORKSPACE = os.environ.get("REGEN_WORKSPACE", os.path.join(ROOT, "workspace"))
PACKAGE = os.path.join(ROOT, "engine")


def profile_file(name):
    path = os.path.join(PROFILE, name)
    if not os.path.exists(path):
        raise SystemExit(f"missing {path}: copy profile.example/ to profile/ and fill in your own facts and presets")
    return path


@contextmanager
def in_workspace():
    """Run a stage with the workspace as the working directory, so relative state files land there."""
    os.makedirs(WORKSPACE, exist_ok=True)
    prev = os.getcwd()
    os.chdir(WORKSPACE)
    try:
        yield WORKSPACE
    finally:
        os.chdir(prev)


def proof_file(path, workspace=None):
    """The proof on disk for an event's proof path, or None. 11-12 (user): screenshots became text; an old event names
    proof/X.png while the file is now proof/X.txt, so either one proves the submission."""
    if not path:
        return None
    for p in (path, os.path.splitext(path)[0] + ".txt"):
        full = os.path.join(workspace or WORKSPACE, p)
        if os.path.exists(full):
            return full
    return None
