#!/usr/bin/env python3
"""Backend-local seed entrypoint for CI and smoke tests."""

from app.config import get_settings
from app.database import ClickHouse
from app.seed import seed_demo_data


def main() -> None:
    db = ClickHouse(get_settings())
    db.connect()
    seed_demo_data(db)
    print("ThreatLens demo data is ready.")


if __name__ == "__main__":
    main()
