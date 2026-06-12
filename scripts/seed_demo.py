#!/usr/bin/env python3
"""Seed ThreatLens demo data into ClickHouse.

Run from the repository root after installing backend dependencies:
  python scripts/seed_demo.py
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.database import ClickHouse  # noqa: E402
from app.seed import seed_demo_data  # noqa: E402


def main() -> None:
    db = ClickHouse(get_settings())
    db.connect()
    seed_demo_data(db)
    print("ThreatLens demo data is ready.")


if __name__ == "__main__":
    main()
