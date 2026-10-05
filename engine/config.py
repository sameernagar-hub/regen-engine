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
