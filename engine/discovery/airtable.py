"""Read a public Airtable shared view (the job boards behind newgrad-jobs.com and similar sites).

A shared view page embeds a signed `readSharedViewData` URL; requesting it with the page's cookies
returns the whole table as JSON. Read-only, public data, discovery only.
"""
import json, re, urllib.request, http.cookiejar

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def read_view(share_url, timeout=30):
    """share_url: https://airtable.com/[embed/]appXXX/shrYYY -> list of {column name: value} dicts."""
    m = re.search(r"(app\w+)/(shr\w+)", share_url)
    if not m:
        raise ValueError(f"not an Airtable share url: {share_url}")
    app, shr = m.groups()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    page = op.open(urllib.request.Request(f"https://airtable.com/embed/{app}/{shr}", headers={"User-Agent": UA}), timeout=timeout).read().decode("utf-8", "replace")
    u = re.search(r'urlWithParams: "([^"]+)"', page)
    if not u:
        raise RuntimeError(f"Airtable page layout changed: no readSharedViewData url for {shr}")
    path = u.group(1).encode().decode("unicode_escape")
    hd = {"User-Agent": UA, "x-airtable-application-id": app, "x-requested-with": "XMLHttpRequest",
          "x-time-zone": "America/Los_Angeles", "x-user-locale": "en"}
    data = json.loads(op.open(urllib.request.Request("https://airtable.com" + path, headers=hd), timeout=timeout).read())
    table = data["data"]["table"]
    cols = {c["id"]: c for c in table["columns"]}
    # select columns store choice ids; map them back to names
    choice = {cid: {k: v["name"] for k, v in ((c.get("typeOptions") or {}).get("choices") or {}).items()} for cid, c in cols.items()}
    rows = []
    for r in table["rows"]:
        row = {}
        for cid, v in r.get("cellValuesByColumnId", {}).items():
            if cid not in cols:
                continue
            ch = choice.get(cid)
            if ch:
                v = [ch.get(x, x) for x in v] if isinstance(v, list) else ch.get(v, v)
            row[cols[cid]["name"]] = v
        row["_created"] = r.get("createdTime")
        rows.append(row)
    return rows
