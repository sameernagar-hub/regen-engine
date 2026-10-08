"""Privacy gate for the public repo: nothing personal may ever be committed or merged.

Three modes, one set of rules:

  python scripts/privacy_scan.py                  LOCAL: check tracked files + commit metadata against your private terms
  python scripts/privacy_scan.py --history        ...and every blob ever committed (slower)
  python scripts/privacy_scan.py --update-denylist   write .privacy/denylist.json (keyed fingerprints of your private terms)
  python scripts/privacy_scan.py --ci             CI: generic PII + forbidden paths + commit emails + fingerprint denylist
  python scripts/privacy_scan.py --install-hook   run the LOCAL check before every `git push`

Private terms come from your git-ignored data and are never printed in full or committed in clear text:
  profile/presets.json, profile/fact_bank.json, workspace/events.jsonl (companies), profile/private_terms.txt
The committed denylist holds only HMAC-SHA256 fingerprints keyed with a secret (profile/.privacy_key locally,
the PRIVACY_KEY secret in GitHub Actions). Without the key the fingerprints reveal nothing, not even guessable names.
"""
import hashlib, hmac, json, os, re, secrets, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DENYLIST = os.path.join(ROOT, ".privacy", "denylist.json")
KEYFILE = os.path.join(ROOT, "profile", ".privacy_key")
MAX_NGRAM = 7
SHOW = "--show" in sys.argv  # local terminal only: print matches unmasked to review them

# public by design (the account and repo), or too generic to be personal
PUBLIC_OK = {"sameernagar hub", "regen engine", "united states", "computer science", "california", "remote", "software engineer",
             "github", "linkedin", "master s", "bachelor s", "san francisco bay area", "https github com sameernagar hub"}
SKIP_PRESET_KEYS = {"city", "state", "state_abbr", "country", "grad_year", "years_experience", "degree", "major", "how_heard",
                    "eeo", "submit_policy", "start_date", "salary_expectation", "preferred_location", "github"}
# company names from the event log that are also everyday words ("applied" is an Ashby board slug); treating them as
# private terms flags half the repo, which trains everyone to ignore the gate
COMMON_WORD_COMPANIES = {"clear", "handshake", "chalk", "applied", "affirm", "ramp", "compass", "scale", "figure", "notion", "current", "atoms",
                         "mercury", "anchor", "persona", "together", "modal", "pylon"}
ALLOW_FILES ={"engine/discovery/boards.example.txt"}  # a public list of company job boards, not applications
FORBIDDEN = re.compile(r"^(profile/|workspace/(?!\.gitkeep$)|\.env$|\.env\.local$|\.insforge/)|\.(pdf|docx)$", re.I)

GENERIC = [  # (name, regex) for PII that must never be committed by anyone
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@(?!(?:example\.(?:com|org)|users\.noreply\.github\.com|noreply\.github\.com))[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("phone", re.compile(r"(?<![\d.])(?:\+?1[ .-]?)?\(?[2-9]\d{2}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)")),
    ("ssn", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")),
    ("api key", re.compile(r"\b(sk-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,})\b")),
    ("private key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----")),
]
PHONE_OK = re.compile(r"555[ .-]01\d\d|555-010-0000|555\) 555-5555|555-555-5555")   # fictional numbers
EMAIL_OK_LOCAL = re.compile(r"^(noreply|no-reply|you|jane\.doe|name|user)@", re.I)


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def norm(text):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def collect_terms():
    terms = set()
    prof = os.path.join(ROOT, "profile")

    def add(t):
        n = norm(str(t))
        if len(n) >= 3 and n not in PUBLIC_OK and not n.isdigit() and len(n.split()) <= MAX_NGRAM:
            terms.add(n)

    p = os.path.join(prof, "presets.json")
    if os.path.exists(p):
        for k, v in json.load(open(p, encoding="utf-8")).items():
            if not isinstance(v, str) or v.startswith("<") or v in ("Yes", "No") or k in SKIP_PRESET_KEYS:
                continue
            add(v)
            if k == "phone":
                d = re.sub(r"\D", "", v)[-10:]
                add(d); add(f"{d[:3]} {d[3:6]} {d[6:]}")
            if k == "linkedin":
                add(v.rstrip("/").rsplit("/", 1)[-1])
            if k == "email":
                add(v.split("@")[0])
    p = os.path.join(prof, "fact_bank.json")
    if os.path.exists(p):
        fb = json.load(open(p, encoding="utf-8"))
        for role in fb.get("roles", {}).values():
            add(role[0])
        for proj in fb.get("projects", {}).values():
            add(re.split(r"\s+--\s+", proj[0])[0])
        for e, _d in fb.get("education", []):
            for part in re.split(r"--|\|", e):
                if re.search(r"university|vishwavidyalaya|college|institute", part, re.I):
                    add(part.split(",")[0]); add(part)
        name = (fb.get("contact") or {}).get("name", "")
        if name:
            add(name)
            for n in name.split():
                if len(n) >= 4:
                    add(n)
    p = os.path.join(ROOT, "workspace", "events.jsonl")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            co = (e.get("company") or (e.get("job") or "").partition(" - ")[0]).strip()
            if len(co) >= 4 and norm(co) not in COMMON_WORD_COMPANIES:
                add(co)
    p = os.path.join(prof, "private_terms.txt")
    if os.path.exists(p):
        for t in open(p, encoding="utf-8"):
            if t.strip() and not t.startswith("#"):
                add(t.strip())
    return terms


def ngrams(text):
    words = norm(text).split()
    for i in range(len(words)):
        for n in range(1, MAX_NGRAM + 1):
            if i + n <= len(words):
                yield " ".join(words[i:i + n])


def fp(key, term):
    return hmac.new(key, term.encode(), hashlib.sha256).hexdigest()[:32]


def mask(t):
    return t if SHOW else (t[:2] + "…" + t[-1:] if len(t) > 4 else "…")


def tracked_texts():
    for f in git("ls-files").splitlines():
        p = os.path.join(ROOT, f)
        if f in ALLOW_FILES or not os.path.isfile(p):
            continue
        try:
            yield f, open(p, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue


def check_terms(texts, match):
    """match(ngram) -> bool. Returns [(file, term-ish)]."""
    hits = []
    for name, text in texts:
        for g in ngrams(text):
            if match(g):
                hits.append((name, g)); break
    return hits


def check_generic(texts):
    hits = []
    for name, text in texts:
        if name.startswith("tests/fixtures/"):
            continue
        for label, rx in GENERIC:
            for m in rx.finditer(text):
                s = m.group(0)
                if label == "phone" and PHONE_OK.search(s):
                    continue
                if label == "email" and EMAIL_OK_LOCAL.search(s):
                    continue
                hits.append((name, f"{label}: {mask(s)}"))
    return hits


def accepted_history():
    p = os.path.join(ROOT, ".privacy", "accepted_history.txt")
    return {l.strip() for l in open(p) if l.strip() and not l.startswith("#")} if os.path.exists(p) else set()


def commit_emails(rev_range):
    bad, legacy = [], accepted_history()
    for line in git("log", "--format=%H|%ae|%ce", *([rev_range] if rev_range else ["--all"])).splitlines():
        h, ae, ce = (line.split("|") + ["", ""])[:3]
        if h in legacy:
            continue
        h = h[:8]
        for e in (ae, ce):
            if e and not re.search(r"users\.noreply\.github\.com$|^noreply@github\.com$|@example\.com$", e):
                bad.append((h, f"commit email {mask(e)} is not a noreply address"))
    return bad


def main(argv):
    if "--install-hook" in argv:
        hook = os.path.join(ROOT, ".git", "hooks", "pre-push")
        open(hook, "w", newline="\n").write(  # resolve the main checkout, so pushes from linked worktrees are gated too
            "#!/bin/sh\nROOT=\"$(cd \"$(git rev-parse --git-common-dir)/..\" && pwd)\"\n"
            "(cd \"$ROOT\" && python scripts/privacy_scan.py) || { echo 'privacy_scan: push blocked'; exit 1; }\n")
        os.chmod(hook, 0o755); print("pre-push hook installed"); return 0

    if "--update-denylist" in argv:
        os.makedirs(os.path.dirname(KEYFILE), exist_ok=True)
        if not os.path.exists(KEYFILE):
            open(KEYFILE, "w").write(secrets.token_hex(32))
        key = bytes.fromhex(open(KEYFILE).read().strip())
        terms = collect_terms()
        os.makedirs(os.path.dirname(DENYLIST), exist_ok=True)
        json.dump({"about": "HMAC-SHA256 fingerprints of private terms (normalized n-grams). Useless without the PRIVACY_KEY secret.",
                   "max_ngram": MAX_NGRAM, "fingerprints": sorted(fp(key, t) for t in terms)}, open(DENYLIST, "w"), indent=0)
        print(f"wrote {len(terms)} fingerprints -> .privacy/denylist.json; key stays in profile/.privacy_key (git-ignored)")
        print("set the CI secret once:  gh secret set PRIVACY_KEY < profile/.privacy_key")
        return 0

    texts = list(tracked_texts())
    problems = [(f, "forbidden path (private data)") for f in git("ls-files").splitlines() if FORBIDDEN.search(f)]
    problems += check_generic(texts)

    if "--ci" in argv:
        rng = os.environ.get("PRIVACY_RANGE", "")
        problems += commit_emails(rng or None)
        key = os.environ.get("PRIVACY_KEY", "").strip()
        if key and os.path.exists(DENYLIST):
            k = bytes.fromhex(key)
            deny = set(json.load(open(DENYLIST))["fingerprints"])
            problems += [(f, "matches a private term (fingerprint)") for f, _ in check_terms(texts, lambda g: fp(k, g) in deny)]
        elif os.path.exists(DENYLIST):
            print("::warning::PRIVACY_KEY secret not available (e.g. a fork PR): fingerprint check skipped; generic checks ran")
    else:
        terms = collect_terms()
        if not terms:
            print("no private profile on this machine: only generic checks ran")
        problems += [(f, f"private term: {mask(g)}") for f, g in check_terms(texts, lambda g: g in terms)]
        problems += commit_emails(None)
        if "--history" in argv and terms:
            seen = set()
            for line in git("rev-list", "--all", "--objects").splitlines():
                sha, _, path = line.partition(" ")
                if not path or sha in seen or path in ALLOW_FILES:
                    continue
                seen.add(sha)
                if git("cat-file", "-t", sha).strip() != "blob":
                    continue
                for _f, g in check_terms([(path, git("cat-file", "-p", sha))], lambda g: g in terms):
                    problems.append((f"{path}@{sha[:8]}", f"private term in history: {mask(g)}"))
    for f, why in problems:
        print(f"  {f}: {why}")
    print("LEAKS FOUND" if problems else "privacy check: clean")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
