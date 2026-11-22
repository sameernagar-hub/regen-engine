"""regen-engine MCP (stdio) that follows the live bank.

When the stack is running, the stdio server runs inside deploy-pipeline-1 against the Docker volumes (the same data
the engine writes, writes enabled). When it is down, it runs from this checkout against the local folders (stale, read-only).
Before this (11-21) the host copy always read the local folders, so its counts lagged the running engine.

.mcp.json:  "command": "py", "args": ["-3.14", "scripts/mcp_stdio.py"]
"""
import os
import subprocess
import sys

CONTAINER = os.environ.get("REGEN_MCP_CONTAINER", "deploy-pipeline-1")


def running(name):
    try:
        out = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() == "true"
    except Exception:
        return False


def main():
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "MSYS_NO_PATHCONV": "1"}
    if running(CONTAINER):  # uid 10001 = the engine user, so nothing it writes becomes root-owned
        cmd = ["docker", "exec", "-i", "-u", "10001", "-e", "REGEN_MCP_WRITE=1", "-e", "PYTHONIOENCODING=utf-8",
               CONTAINER, "python", "-m", "engine", "mcp"]
    else:
        env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = [sys.executable, "-m", "engine", "mcp"]
    sys.exit(subprocess.run(cmd, env=env).returncode)


if __name__ == "__main__":
    main()
