"""`python -m engine inspect <job url> [--show]`: read an application form without filling it.

Prints every field: required?, widget type, its options (for selects/radios), and the answer the
engine would give (or UNKNOWN -> this job would land in the human queue). Headless by default.
Use it before a batch to see which questions need an `extra` answer, and to debug adapters.
"""
import re, sys
from playwright.sync_api import sync_playwright

from engine.apply.runner import answer_for, gh_embed_url

FIELDS_JS = r"""
(sel) => [...document.querySelectorAll(sel)].map(f => {
  const lab = f.querySelector('label, legend');
  const opts = [...f.querySelectorAll('input[type=radio], input[type=checkbox]')].map(c =>
      ((c.closest('label') || document.querySelector(`label[for='${c.id}']`) || c.parentElement).innerText || '').trim()).filter(Boolean);
  const kind = f.querySelector('input[role=combobox], [class*=select__control]') ? 'select'
             : f.querySelector('input[type=radio]') ? 'radio' : f.querySelector('input[type=checkbox]') ? 'checkbox'
             : f.querySelector('textarea') ? 'textarea' : f.querySelector('input[type=file]') ? 'file'
             : f.querySelector('input') ? 'text' : (f.querySelectorAll('button').length ? 'buttons' : '?');
  return {label: lab ? lab.innerText.trim() : '', kind, opts, required: !!(lab && lab.innerText.includes('*')) || !!f.querySelector('[required],[aria-required=true]')};
}).filter(x => x.label)
"""


def inspect(url, show=False):
    ash = "ashbyhq" in url
    if ash:
        url = url.split("?")[0].rstrip("/")
        url = url if url.endswith("/application") else url + "/application"
        sel = ".ashby-application-form-field-entry"
    else:
        url = gh_embed_url(url)
        sel = ".field-wrapper, fieldset, .checkbox, .eeoc__question, .education--container .field-wrapper"
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not show)
        page = b.new_page()
        page.goto(url)
        page.wait_for_timeout(4000)
        fields = page.evaluate(FIELDS_JS, sel)
        b.close()
    seen, unknown = set(), 0
    for f in fields:
        key = f["label"][:80]
        if key in seen:
            continue
        seen.add(key)
        label = f["label"].rstrip("*").strip()
        ans = answer_for(label, {})
        if ans is None and f["required"] and f["kind"] != "file":
            unknown += 1
        print(f"{'*' if f['required'] else ' '} [{f['kind']:<8}] {' '.join(label.split())[:90]}")
        if f["opts"]:
            print(f"      options: {' | '.join(o[:40] for o in f['opts'][:8])}")
        print(f"      -> {ans if ans is not None else ('UNKNOWN' if f['kind'] != 'file' else '(resume upload)')}")
    print(f"{len(seen)} fields, {unknown} required without an answer")
    return unknown


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    inspect(argv[0], show="--show" in argv)


if __name__ == "__main__":
    main()
