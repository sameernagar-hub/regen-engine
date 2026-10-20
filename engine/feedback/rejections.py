"""Rejection feedback: read the inbox, compare rejected job descriptions with the rest, and teach the fit gate.

  python -m engine feedback              one pass: IMAP (if .env has the app password) -> outcomes -> analysis
  python -m engine feedback --watch [m]  the `feedback` container: one pass every m minutes (default 30)
  python -m engine feedback --no-imap    analyze the outcomes already in the ledger (no mail read)

Each pass writes workspace/feedback.md (what rejected JDs asked for that the others did not) and
workspace/learned_gate.json, which tailor.fit() reads. Candidates need MIN_REJ rejected JDs, a rejection rate LIFT
times the baseline and no OA / interview / offer where they appear; they stay "proposed" (reported, never blocking)
until the binomial tail P(>= rejected | seen, baseline) times the number of phrases tested is below ALPHA
(Bonferroni). The first pass on 42 rejections showed why: every raw candidate was boilerplate ("problem solving"). Phrases the Fact Bank already covers never become blockers: the gate learns what the
candidate lacks, not what the market dislikes. Set "status": "off" on a rule (or `feedback --off <phrase>`) to
keep it from ever blocking again; the next pass keeps that choice. Read-only on the mailbox; O(J * W) per pass
for J job descriptions of W words.
"""
import collections, glob, html, json, math, os, re, sys, time

from engine.config import WORKSPACE
from engine.feedback.events import read, record

GATE = os.path.join(WORKSPACE, "learned_gate.json")
MIN_REJ = 4        # rejected JDs a phrase must appear in
LIFT = 1.5         # its rejection rate vs the baseline rejection rate
MAX_RULES = 40
ALPHA = 0.05       # family-wise error rate for promoting a phrase to a blocker
# only requirement-like sentences: boilerplate (benefits, EEO, about-us) would otherwise dominate
CUE = re.compile(r"\b(experience|required|requirements?|must|degree|years?|proficien\w*|familiar\w*|expert\w*|"
                 r"knowledge of|background in|qualifications?|you have|you.ll have|minimum|preferred)\b")
STOP = set("a an and or the of to in for with on at by from as is are be be you your we our us this that it its "
           "will can have has who what which their they them other such into using use including etc per not "
           "years year experience required requirements preferred qualifications minimum must strong ability "
           "skills skill knowledge work working team plus least degree".split())
WORD = re.compile(r"[a-z][a-z0-9+#.]{1,}")


def jd_texts():
    """{url: plain lowercase JD text} from workspace/jd (the raw postings saved at batch time). O(files)."""
    out = {}
    for f in glob.glob(os.path.join(WORKSPACE, "jd", "*.json")):
        try:
            j = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        url = (j.get("absolute_url") or j.get("jobUrl") or j.get("applyUrl") or "").split("?")[0]
        text = j.get("content") or j.get("descriptionHtml") or j.get("descriptionPlain") or j.get("description") or ""
        if url and text:
            out[url] = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(html.unescape(text))).split()).lower()
    return out


def grams(text):
    """Set of 2-3 word phrases from requirement sentences, without stopword edges. O(W)."""
    out = set()
    for s in re.split(r"(?<=[.!?;•])\s+|\s[-*•]\s", text):
        if not CUE.search(s):
            continue
        w = [t.rstrip(".") for t in WORD.findall(s)]  # keep "node.js", drop a sentence's final period
        for n in (2, 3):
            for i in range(len(w) - n + 1):
                g = w[i:i + n]
                if g[0] in STOP or g[-1] in STOP or len(set(g)) < n:
                    continue
                out.add(" ".join(g))
    return out


def labeled():
    """[(job, url, label)] for submitted applications: label = rejection | positive | pending."""
    url_of = {}
    for e in read("application"):
        if (e.get("status") or "").startswith("SUBMITTED") and e.get("url") and not e.get("dry"):
            url_of[e["job"]] = e["url"].split("?")[0]
    outs = collections.defaultdict(set)
    for o in read("outcome"):
        for j in o.get("jobs") or []:
            outs[j].add(o.get("outcome"))
    lab = []
    for job, url in url_of.items():
        o = outs.get(job, set())
        lab.append((job, url, "positive" if o & {"oa", "interview", "offer"} else "rejection" if "rejection" in o else "pending"))
    return lab


def covered(phrase, vocab):
    """True when the Fact Bank already has this skill (then a rejection is not about lacking it)."""
    toks = [t for t in phrase.split() if t not in STOP]
    return any(t in vocab for t in toks) or phrase in vocab


def analyze(texts=None, lab=None, vocab=None):
    """Score phrases by how much more often they appear in rejected JDs. Returns (rules, stats)."""
    texts = jd_texts() if texts is None else texts
    lab = labeled() if lab is None else lab
    if vocab is None:
        from engine.tailoring.tailor import vocabulary
        vocab = vocabulary()
    rows = [(job, label, grams(texts[url])) for job, url, label in lab if url in texts]
    rej = [r for r in rows if r[1] == "rejection"]
    if not rej:
        return [], {"with_jd": len(rows), "rejected": 0}
    base = len(rej) / len(rows)
    seen, bad, good = collections.Counter(), collections.Counter(), collections.Counter()
    for _, label, gs in rows:
        for g in gs:
            seen[g] += 1
            if label == "rejection":
                bad[g] += 1
            elif label == "positive":
                good[g] += 1
    rules, tested = [], sum(1 for g in seen if seen[g] >= MIN_REJ)
    for g, b in bad.items():
        if b < MIN_REJ or good[g] or covered(g, vocab):
            continue
        rate = b / seen[g]
        if rate >= min(1.0, LIFT * base):
            p = tail(b, seen[g], base) * max(1, tested)
            rules.append({"phrase": g, "rejected": b, "seen": seen[g], "rate": round(rate, 2),
                          "lift": round(rate / base, 2) if base else None, "p_adj": round(min(1.0, p), 4),
                          "evidence": "significant" if p < ALPHA else "weak"})
    rules.sort(key=lambda r: (r["p_adj"], -r["rejected"]))
    # drop a phrase contained in a stronger one already kept ("distributed systems" vs "large distributed systems")
    kept = []
    for r in rules:
        if not any(r["phrase"] in k["phrase"] or k["phrase"] in r["phrase"] for k in kept):
            kept.append(r)
    stats = {"with_jd": len(rows), "rejected": len(rej), "positive": sum(1 for r in rows if r[1] == "positive"),
             "baseline_rejection_rate": round(base, 2), "phrases_tested": tested}
    return kept[:MAX_RULES], stats


def tail(k, n, p):
    """P(X >= k) for X ~ Binomial(n, p). O(n)."""
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def load_gate():
    try:
        return json.load(open(GATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"rules": []}


def save_gate(rules, stats):
    """Merge with the old gate: a rule the user turned off stays off; one with no evidence left is dropped."""
    old = {r["phrase"]: r for r in load_gate().get("rules", [])}
    for r in rules:
        r["status"] = ("off" if old.get(r["phrase"], {}).get("status") == "off"
                       else "active" if r.get("evidence") == "significant" else "proposed")
    offs = [r for p, r in old.items() if r.get("status") == "off" and p not in {x["phrase"] for x in rules}]
    gate = {"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "stats": stats, "rules": rules + offs}
    tmp = GATE + ".tmp"
    json.dump(gate, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, GATE)
    return gate


def report(gate, causes):
    s = gate.get("stats", {})
    lines = ["# Rejection feedback (auto-generated by `python -m engine feedback`)", "",
             f"Updated {gate.get('updated')}. {s.get('rejected', 0)} rejected of {s.get('with_jd', 0)} submitted JDs on file "
             f"(baseline rejection rate {s.get('baseline_rejection_rate', '?')}); {s.get('positive', 0)} with an OA / interview / offer.", "",
             "## Learned fit-gate phrases", "A phrase blocks new postings only while `active` (significant after the multiple-test correction); "
             "`proposed` ones are watched, never blocking. "
             "Turn one off: `python -m engine feedback --off \"<phrase>\"`.", "",
             "| phrase | rejected JDs | JDs seen | rejection rate | lift | p (adjusted) | status |", "|---|---|---|---|---|---|---|"]
    for r in gate.get("rules", []):
        lines.append(f"| {r['phrase']} | {r.get('rejected', '')} | {r.get('seen', '')} | {r.get('rate', '')} | {r.get('lift', '')} | {r.get('p_adj', '')} | {r['status']} |")
    lines += ["", "## Would today's gate have caught them?", "| blocker found now | rejected applications |", "|---|---|"]
    for k, n in causes.most_common():
        lines.append(f"| {k} | {n} |")
    open(os.path.join(WORKSPACE, "feedback.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def causes(texts, lab):
    """Re-run the current fit gate on every rejected JD: which blocker would now stop it (or 'none: generic')."""
    from engine.tailoring.tailor import fit
    c = collections.Counter()
    for _, url, label in lab:
        if label == "rejection" and url in texts:
            b = fit(texts[url])
            c[b[0].split(":")[0] if b else "none (generic reject)"] += 1
    return c


def run_pass(imap=True, days=3):
    got = 0
    if imap:
        try:
            from engine.feedback.inbox import fetch_imap, ingest
            got = len(ingest(fetch_imap(days)))
        except SystemExit as e:  # no app password in .env: analyze what the ledger already has
            print(f"feedback: IMAP skipped ({e})", flush=True)
        except Exception as e:
            print(f"feedback: IMAP failed ({type(e).__name__}: {e})", flush=True)
    texts, lab = jd_texts(), labeled()
    rules, stats = analyze(texts, lab)
    gate = save_gate(rules, stats)
    report(gate, causes(texts, lab))
    active = sum(1 for r in gate["rules"] if r["status"] == "active")
    record("feedback", new_outcomes=got, rejected=stats.get("rejected", 0), rules=active)
    print(f"feedback: {got} new outcomes, {stats.get('rejected', 0)} rejected JDs, {active} active learned rules", flush=True)
    return {"new_outcomes": got, "active_rules": active, **stats}


def turn_off(phrase):
    gate = load_gate()
    hit = [r for r in gate.get("rules", []) if r["phrase"] == phrase]
    for r in hit:
        r["status"] = "off"
    if not hit:
        gate.setdefault("rules", []).append({"phrase": phrase, "status": "off"})
    json.dump(gate, open(GATE, "w", encoding="utf-8"), indent=1)
    print(f"off: {phrase}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--off"]:
        return turn_off(" ".join(argv[1:]).strip().lower())
    imap = "--no-imap" not in argv
    if "--watch" not in argv:
        return run_pass(imap)
    i = argv.index("--watch")
    minutes = int(argv[i + 1]) if len(argv) > i + 1 and argv[i + 1].isdigit() else 30
    from engine.supervisor import beat
    while True:
        beat("feedback", state="scanning")
        try:
            r = run_pass(imap)
            beat("feedback", state="watching", **{k: r.get(k) for k in ("rejected", "active_rules", "new_outcomes")})
        except Exception as e:  # one bad pass must not stop the loop
            print(f"feedback: pass failed ({type(e).__name__}: {e})", flush=True)
            beat("feedback", state=f"error: {type(e).__name__}")
        for _ in range(minutes):
            time.sleep(60)
            beat("feedback", state="watching")


if __name__ == "__main__":
    main()
