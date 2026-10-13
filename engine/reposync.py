"""`python -m engine reposync [--once]`: the repo-sync container keeps GitHub current without anyone pushing.

Every REGEN_SYNC_MIN minutes (15):
  feed   rebuild the anonymized public feed from the bank (engine/live/export.py, with its leak airbag) and push it
         to gh-pages when it changed: the Render site reads it, so the public page stays live.
  code   compare the host repo's local `main` (bind-mounted read-only at /src) with GitHub's main. Commits that are
         only local are checked in a clean worktree (privacy scan with the user's real terms + the full test suite)
         and, when both pass, pushed to the bot branch `bot/sync`, with a pull request to main opened or updated.
         The user merges. Uncommitted work is never pushed.

Guardrails (no loopholes by construction, each one tested in tests/test_core.py):
  - push targets are an allowlist: gh-pages and bot/* only. main (or anything else) raises GuardError before git runs.
  - no force-push, except --force-with-lease on the bot branch it owns.
  - the token is read from the Docker secret per command and passed as an HTTP header; it is never written to git
    config, a remote URL, a log line or an event. Command output is scrubbed of it before anything is printed.
  - KILL (workspace/KILL) holds every push; a diverged history (GitHub main not an ancestor of local main) is
    reported, never "fixed".
  - every action is an audited `reposync` event; the container beats into workspace/fleet/ like the others, so the
    supervisor sees it and restarts it when it goes silent.
"""
import base64, json, os, subprocess, sys, time, urllib.request

from engine.config import WORKSPACE
from engine.supervisor import beat

REPO = os.environ.get("REGEN_REPO_DIR", "/repo")          # the container's own clone (named volume)
SRC = os.environ.get("REGEN_REPO_SRC", "/src")            # the host repo, read-only
URL = os.environ.get("REGEN_REPO_URL", "https://github.com/sameernagar-hub/regen-engine.git")
SLUG = URL.rstrip("/").removesuffix(".git").split("github.com/")[-1]
TOKEN_FILE = os.environ.get("REGEN_GH_TOKEN_FILE", "/run/secrets/gh_token")
BOT = "bot/sync"
ALLOWED = ("refs/heads/gh-pages", "refs/heads/bot/")
EVERY = float(os.environ.get("REGEN_SYNC_MIN", "15")) * 60
AUTHOR = ["-c", "user.name=sameernagar-hub", "-c", "user.email=180349498+sameernagar-hub@users.noreply.github.com"]


# git honors safe.directory only from global/system config (not -c, not GIT_CONFIG_*), and the upload-pack it spawns
# to read the host repo (/src, owned by another uid) needs it too: a private global config file holds just that.
# Credential prompts are off: no token means fail, never ask.
GLOBAL_CFG = os.path.join(os.environ.get("TMPDIR", "/tmp"), "reposync.gitconfig")
GIT_ENV = dict(os.environ, GIT_CONFIG_GLOBAL=GLOBAL_CFG, GIT_TERMINAL_PROMPT="0")


def _global_cfg():
    if not os.path.exists(GLOBAL_CFG):
        with open(GLOBAL_CFG, "w", encoding="utf-8") as f:
            f.write("[safe]\n\tdirectory = *\n")


class GuardError(RuntimeError):
    pass


def token():
    try:
        t = open(TOKEN_FILE, encoding="utf-8").read().strip()
    except OSError:
        return None
    return t if t and not t.startswith("PASTE_") else None


def _scrub(text, t):
    return text.replace(t, "***") if t else text


def git(*args, cwd=None, auth=False, check=True, timeout=300):
    """Run git; with auth the token rides in an http.extraHeader for this one command only. Returns stdout."""
    t = token() if auth else None
    _global_cfg()
    pre = ["git", "-c", "credential.helper="]
    if t:
        b = base64.b64encode(f"x-access-token:{t}".encode()).decode()
        pre += ["-c", f"http.extraHeader=Authorization: Basic {b}"]
    r = subprocess.run(pre + list(args), cwd=cwd or REPO, capture_output=True, text=True, timeout=timeout, env=GIT_ENV)
    if check and r.returncode:
        raise RuntimeError(_scrub(f"git {args[0]}: {(r.stderr or r.stdout).strip()[-300:]}", t))
    return r.stdout.strip()


def push(src, dst, lease=None):
    """The only way this module pushes. dst must be on the allowlist; force only as a lease on a bot branch."""
    if not dst.startswith("refs/heads/") or not any(dst == a or (a.endswith("/") and dst.startswith(a)) for a in ALLOWED):
        raise GuardError(f"push to {dst} refused: only gh-pages and bot/* are allowed")
    if lease is not None and not dst.startswith("refs/heads/bot/"):
        raise GuardError("force-with-lease is only allowed on bot/* branches")
    if os.path.exists(os.path.join(WORKSPACE, "KILL")):
        raise GuardError("kill switch is on: no pushes")
    args = ["push", "--no-verify", URL, f"{src}:{dst}"]
    if lease is not None:
        args.insert(1, f"--force-with-lease={dst}:{lease}")
    return git(*args, auth=True)


def audit(action, **kw):
    print(f"reposync: {action} {kw or ''}".rstrip(), flush=True)
    try:
        from engine.feedback.events import record
        record("reposync", action=action, **kw)
    except Exception:
        pass


def ensure_clone():
    if not os.path.isdir(os.path.join(REPO, ".git")):
        os.makedirs(REPO, exist_ok=True)
        git("clone", "--no-checkout", URL, REPO, cwd="/", auth=True)
    git("fetch", "--prune", URL, "+refs/heads/main:refs/remotes/origin/main", "+refs/heads/gh-pages:refs/remotes/origin/gh-pages",
        f"+refs/heads/{BOT}:refs/remotes/origin/{BOT}", auth=True, check=False)


def sync_feed():
    """Rebuild replay.json from the bank and push gh-pages when it changed."""
    from engine.live import export as X
    try:
        d = X.build(7)
    except SystemExit as e:  # the leak airbag refused: nothing is published, the reason is audited
        audit("feed_blocked", reason=str(e)[:200])
        return "blocked"
    wt = os.path.join(REPO, ".pages")
    if not os.path.isdir(wt):
        git("worktree", "add", "-f", "--detach", wt, "refs/remotes/origin/gh-pages")
    git("checkout", "--detach", "refs/remotes/origin/gh-pages", cwd=wt)
    git("reset", "--hard", "refs/remotes/origin/gh-pages", cwd=wt)
    for f in ("index.html", "replay.json"):
        with open(os.path.join(X.SITE, f), "rb") as a, open(os.path.join(wt, f), "wb") as b:
            b.write(a.read())
    if not git("status", "--porcelain", cwd=wt):
        return "unchanged"
    git("add", "-A", cwd=wt)
    git(*AUTHOR, "commit", "-m", "public feed: anonymized replay " + time.strftime("%Y-%m-%d %H:%M"), cwd=wt)
    push("HEAD", "refs/heads/gh-pages")
    audit("feed_pushed", verified=d["verified"], events=len(d["events"]))
    return "pushed"


def _check(sha):
    """Privacy scan (with the user's real terms) + test suite on a clean checkout of sha. Returns (ok, why)."""
    wt = os.path.join(REPO, ".check")
    if not os.path.isdir(wt):
        git("worktree", "add", "-f", "--detach", wt, sha)
    git("checkout", "-f", "--detach", sha, cwd=wt)
    git("clean", "-fdq", cwd=wt)
    for name, target in (("profile", os.environ.get("REGEN_PROFILE", "/data/profile")), ("workspace", WORKSPACE)):
        link = os.path.join(wt, name)
        if not os.path.lexists(link):
            os.symlink(target, link)  # the privacy scan reads private terms from profile/ and workspace/events.jsonl
    env = {k: v for k, v in os.environ.items() if not k.startswith(("REGEN_SMTP", "REGEN_GH"))}
    for cmd in ([sys.executable, "scripts/privacy_scan.py"], [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"]):
        r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, timeout=1800, env=env)
        if r.returncode:
            return False, f"{cmd[-1] if 'pytest' not in cmd else 'tests'}: {(r.stdout + r.stderr).strip().splitlines()[-1:]}"
    return True, "privacy scan clean, tests pass"


def _api(method, path, body=None):
    req = urllib.request.Request(f"https://api.github.com/repos/{SLUG}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token()}", "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def _ancestor(a, b):
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=REPO, capture_output=True,
                          env=GIT_ENV).returncode == 0


def sync_code():
    """Local main commits not on GitHub -> checked -> bot/sync + PR. Returns a short state string."""
    git("fetch", "--no-tags", SRC, "+refs/heads/main:refs/remotes/host/main")
    host = git("rev-parse", "refs/remotes/host/main")
    gh = git("rev-parse", "refs/remotes/origin/main")
    if host == gh or _ancestor(host, gh):  # nothing local that GitHub lacks
        return "in sync"
    if not _ancestor(gh, host):
        audit("diverged", host=host[:10], github=gh[:10])
        return "diverged: needs a human"
    bot = git("rev-parse", "--verify", "-q", f"refs/remotes/origin/{BOT}", check=False)
    if bot == host:
        return "PR up to date"
    ok, why = _check(host)
    if not ok:
        audit("code_blocked", sha=host[:10], reason=why[:200])
        return "blocked: " + why
    push(host, f"refs/heads/{BOT}", lease=bot or "")
    n = int(git("rev-list", "--count", f"{gh}..{host}"))
    owner = SLUG.split("/")[0]
    open_prs = _api("GET", f"/pulls?head={owner}:{BOT}&state=open")
    if open_prs:
        pr = open_prs[0]["html_url"]
    else:
        pr = _api("POST", "/pulls", {"head": BOT, "base": "main", "title": f"Sync {n} local commit(s) from the engine host",
                                     "body": "Opened by the repo-sync container after the privacy scan and the full test "
                                             "suite passed on this exact commit. Merge to deploy (Render builds main).\n\n"
                                             "🤖 Generated with [Claude Code](https://claude.com/claude-code)"})["html_url"]
    audit("code_pushed", sha=host[:10], commits=n, pr=pr)
    return f"PR: {pr}"


def once():
    t = token()
    if not t:
        beat("reposync", state="no GitHub token (.gh_token)")
        return {"state": "no token"}
    if os.path.exists(os.path.join(WORKSPACE, "KILL")):
        beat("reposync", state="held: kill switch")
        return {"state": "held"}
    out = {}
    try:
        ensure_clone()
        out["feed"] = sync_feed()
    except Exception as e:
        out["feed"] = f"error: {_scrub(str(e), t)[:160]}"
    try:
        out["code"] = sync_code()
    except Exception as e:
        out["code"] = f"error: {_scrub(str(e), t)[:160]}"
    beat("reposync", state="synced", **out)
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    while True:
        print(f"reposync: {json.dumps(once())}", flush=True)
        if "--once" in argv:
            return
        for _ in range(int(EVERY // 60)):  # beat every minute while idle so the supervisor knows it is alive
            time.sleep(60)
            beat("reposync", state="idle")


if __name__ == "__main__":
    main()
