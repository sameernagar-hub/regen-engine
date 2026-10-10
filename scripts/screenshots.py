"""Capture README / wiki screenshots from the local web app, with private content hidden.

    python scripts/screenshots.py [base_url]        (default http://127.0.0.1:3000; API + web must be running)

Each shot hides anything that names a company, a person or an answer (narration, applier cards, logs, filters,
tables), so the images show the product, not the user's search. Output: docs/assets/*.png.
"""
import os, sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "assets")
HIDE = {  # page -> CSS that blanks private content
    "/": ".narrator, .waiting, .sr-only { visibility: hidden !important; }",
    "/control": ".appliers, .logbox, [aria-label=Filters], .note { display: none !important; }",
    "/graph": ".panel { display: none !important; }",
}
SHOTS = [("/", "live-dark.png", 1440, 980), ("/control", "control-room.png", 1440, 900), ("/graph", "memory-graph.png", 1440, 860)]


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for path, name, w, h in SHOTS:
            pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1, color_scheme="dark")
            pg.goto(BASE + path, wait_until="load")
            pg.add_style_tag(content=HIDE.get(path, "") + " nextjs-portal { display: none !important; }")
            pg.wait_for_timeout(6000)  # let the bloom / pop animations settle
            pg.screenshot(path=os.path.join(OUT, name))
            print("saved", name)
            pg.close()
        b.close()


if __name__ == "__main__":
    main()
