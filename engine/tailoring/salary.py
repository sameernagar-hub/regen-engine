"""Salary answers (user policy, 2026-10-07): ask within the range the posting offers; with no range, the market rate.

parse_range(text) finds a posted pay range in a job description: "$135,000 - $164,000", "$135K–$164K",
"135,000 to 164,000 USD". Hourly and monthly figures are ignored (they'd be misread as annual). One regex pass, O(n).
expected(job, presets) -> the number to type: the midpoint of the posted range (rounded to $1,000), else
presets["market_salary"]. Plain digits, because number inputs reject "$" and commas.
"""
import html, re

_NUM = r"\$?\s*(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s*[kK]|\d{5,6})"
RANGE = re.compile(_NUM + r"\s*(?:-|–|—|to)\s*" + _NUM + r"(?!\s*(?:/|per)\s*(?:h|hr|hour|month|mo)\b)", re.I)


def _val(s):
    s = s.replace("$", "").replace(",", "").strip().lower()
    return float(s[:-1].strip()) * 1000 if s.endswith("k") else float(s)


def parse_range(text):
    """(low, high) annual USD from a job description, or None."""
    # 11-06: Greenhouse sends the JD HTML-escaped ("&lt;span&gt;$114,983&lt;/span&gt;&lt;span class=divider&gt;&mdash;"):
    # unescape (twice: some boards double-escape) before stripping tags, or the posted range is never seen
    text = html.unescape(html.unescape(text or ""))
    for m in RANGE.finditer(re.sub(r"<[^>]+>", " ", text)):
        lo, hi = _val(m.group(1)), _val(m.group(2))
        if 30_000 <= lo < hi <= 1_000_000:  # annual-looking only
            return int(lo), int(hi)
    return None


def expected(job, presets):
    rng = job.get("salary_range")
    if rng and len(rng) == 2:
        return str(int(round((rng[0] + rng[1]) / 2, -3)))
    return presets.get("market_salary")
