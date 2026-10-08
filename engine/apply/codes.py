"""Match Greenhouse security codes to the jobs waiting for them.

  python -m engine codes '<json from engine/discovery/gmail_codes.js>'

Each waiting job has workspace/codes/<board>_<id>.wait (first line: "Company - Role", second: the form URL).
A code is written to <board>_<id>.txt only when the email names that same company (normalized compare), so a
code is never typed into another company's form. Several codes for one company: the newest (first row) wins.
Already-answered or stale codes are left alone. O(waiting x codes), both tiny.
"""
import json, os, re, sys

from engine.config import WORKSPACE


def _norm(s):
    s = re.sub(r"[,.]?\s+(inc|llc|ltd|corp|corporation|co)\.?$", "", (s or "").strip(), flags=re.I)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def waiting(workspace=None):
    d = os.path.join(workspace or WORKSPACE, "codes")
    out = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".wait") and not os.path.exists(os.path.join(d, f[:-5] + ".txt")):
                first = open(os.path.join(d, f), encoding="utf-8").read().splitlines()[:1]
                out.append((f[:-5], (first[0] if first else "").split(" - ")[0]))
    return out


def match(codes, workspace=None):
    """codes: [{"company", "code"}] newest first -> {slug: code} written to disk."""
    d = os.path.join(workspace or WORKSPACE, "codes")
    written = {}
    for slug, company in waiting(workspace):
        want = _norm(company) or _norm(slug.split("_")[0])
        hit = next((c for c in codes if _norm(c.get("company")) == want and re.fullmatch(r"[A-Za-z0-9]{8}", c.get("code", ""))), None)
        if hit:
            open(os.path.join(d, slug + ".txt"), "w").write(hit["code"])
            written[slug] = hit["code"]
    return written


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    raw = argv[0] if argv else sys.stdin.read()
    codes = json.loads(open(raw).read() if os.path.exists(raw) else raw)
    w = match(codes)
    left = [s for s, _ in waiting()]
    print(f"{len(w)} code(s) written: {', '.join(w) or '-'}; still waiting: {', '.join(left) or '-'}")
