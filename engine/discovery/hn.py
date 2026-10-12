"""Hacker News "Ask HN: Who is hiring?" as a source: new company boards for the scanner, and hiring contacts that
founders publish for applicants (for outreach drafts).

    python -m engine hn [months]        (default 2: this month's thread and last month's)

Each monthly thread has a few hundred top-level posts by the hiring company itself (the thread's rules forbid
recruiters and job boards). From every post:
  boards   -> any Greenhouse / Ashby / Lever / Workable link becomes a board in workspace/boards.json, so the regular
              scan reads every open role there (engine/discovery/ats.py harvest_urls)
  contacts -> an email address the post gives for applying (plain or written out with [at] and [dot]) is saved with the
              company, the post's first line and its link in workspace/outreach/hn_contacts.json. Only addresses the
              poster published are kept; nothing is guessed. Posts that say no recruiters/agencies are fine: this is
              the candidate writing, not an agency.
Read-only public API (hn.algolia.com), two requests per month. O(posts).
"""
import html, json, os, re, sys, urllib.request

from engine.config import WORKSPACE

API = "https://hn.algolia.com/api/v1"
UA = {"User-Agent": "regen-engine (job search; github.com/sameernagar-hub/regen-engine)"}
TLD = r"(?:com|io|ai|co|org|net|dev|app|xyz|us|tech|so|sh|vc|health|bio|inc|gg|me|fm|to|ly|is|so|cloud|systems|energy|finance|world|software|studio|run|build|team|works|page|care)"
# plain addresses, or fully bracketed obfuscation (x [at] y [dot] com). A bare " at " is prose ("reliably at scale"),
# so it is never read as an address (10-11 dry run).
EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\." + TLD + r")(?![A-Za-z0-9-]|\.[A-Za-z0-9])", re.I)
EMAIL_OBF = re.compile(r"\b([A-Za-z0-9._%+-]+)\s*[\[\(\{]\s*at\s*[\]\)\}]\s*([A-Za-z0-9-]+(?:\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*[A-Za-z0-9-]+)+)\b", re.I)
NOT_CONTACT = re.compile(r"^(no-?reply|noreply|privacy|legal|security|abuse|support)$", re.I)


def _get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))


def threads(months=2):
    """Latest `months` "Who is hiring?" story ids, newest first."""
    hits = _get(f"{API}/search_by_date?tags=story,author_whoishiring&hitsPerPage={months * 3 + 3}")["hits"]
    return [(h["objectID"], h["title"]) for h in hits if "who is hiring" in h["title"].lower()][:months]


def _text(c):
    t = html.unescape(re.sub(r"<p>", "\n", c.get("text") or ""))
    return re.sub(r"<[^>]+>", " ", t)


def _hrefs(c):
    return [html.unescape(u) for u in re.findall(r'href="([^"]+)"', c.get("text") or "")]


def email_of(text):
    """First published address in a post (plain or [at]/[dot] bracketed), or None. Never builds one from a name."""
    for m in EMAIL.finditer(text):
        if not NOT_CONTACT.match(m.group(1)):
            return f"{m.group(1)}@{m.group(2)}".lower()
    for m in EMAIL_OBF.finditer(text):
        dom = re.sub(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", ".", m.group(2), flags=re.I)
        if re.search(r"\." + TLD + r"$", dom, re.I) and not NOT_CONTACT.match(m.group(1)):
            return f"{m.group(1)}@{dom}".lower()
    return None


def harvest(months=2):
    from engine.discovery import ats as A
    posts, urls, contacts = 0, [], []
    for sid, title in threads(months):
        story = _get(f"{API}/items/{sid}")
        for c in story.get("children") or []:
            if not c.get("text") or c.get("author") in (None, "whoishiring"):
                continue
            posts += 1
            text = _text(c)
            urls += _hrefs(c) + re.findall(r"https?://[^\s<>\"')]+", text)
            first = text.strip().split("\n")[0][:200]
            mail = email_of(text)
            if mail:
                contacts.append({"company": first.split("|")[0].strip()[:80], "email": mail, "post": first,
                                 "hn": f"https://news.ycombinator.com/item?id={c['id']}", "thread": title,
                                 "us": bool(re.search(r"\b(us|usa|united states|remote|sf|nyc|bay area|california|new york|seattle|boston|austin)\b", first, re.I))})
    b = A.load_boards()
    before = {a: len(set(b[a])) for a in b}
    for a, toks in A.harvest_urls(urls).items():
        b[a] = list(set(b.get(a, [])) | toks)
    A.save_boards(b)
    d = os.path.join(WORKSPACE, "outreach")
    os.makedirs(d, exist_ok=True)
    seen, uniq = set(), []
    for x in contacts:
        if x["email"] not in seen:
            seen.add(x["email"]); uniq.append(x)
    json.dump(uniq, open(os.path.join(d, "hn_contacts.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return posts, {a: (before.get(a, 0), len(set(b[a]))) for a in b}, uniq


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    posts, boards, contacts = harvest(int(argv[0]) if argv else 2)
    for a, (x, y) in boards.items():
        print(f"  {a:<11} {x} -> {y} boards")
    print(f"hn: {posts} posts read; {len(contacts)} published hiring contacts -> workspace/outreach/hn_contacts.json "
          f"({sum(c['us'] for c in contacts)} US/remote)")


if __name__ == "__main__":
    main()
