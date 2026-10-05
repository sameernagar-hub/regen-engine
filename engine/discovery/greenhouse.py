"""Compatibility shim (v0.3 API). Discovery now lives in:

  engine/discovery/ats.py      Greenhouse + Ashby + Lever fetchers and the board registry
  engine/discovery/filters.py  the domain filter (titles, level, US location, excluded employers, dedupe)
  engine/discovery/scan.py     `python -m engine scan`

`from engine.discovery.greenhouse import scan` keeps working and now scans Greenhouse boards only.
"""
import sys

from engine.discovery.filters import load_domain  # noqa: F401  (re-exported for old imports)
from engine.discovery import ats
from engine.discovery.scan import scan as _scan, show


def scan(days=3):
    return _scan(days, only=["greenhouse"])


def scan_board(token):
    return ats.greenhouse(token) or []


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    show(scan(float(argv[0]) if argv else 3))


if __name__ == "__main__":
    main()
