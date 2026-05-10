#!/usr/bin/env python
"""Cron entry point — runs a full scan and sends Telegram alerts.

Used by GitHub Actions on a 3x daily schedule (09:00 / 15:00 / 23:00 JST).
Locally:  python scripts/scan.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Allow running from the repo root without installing the backend as a package.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> int:
    from app.db import init_db
    from app.scanner import scan_all

    init_db()
    summary = scan_all(notify=True)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
