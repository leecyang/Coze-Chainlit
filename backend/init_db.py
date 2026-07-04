#!/usr/bin/env python3
"""Compatibility entrypoint for database maintenance.

The application now runs versioned SQL migrations during startup. This script
is kept for operators that still call `python init_db.py` manually.
"""

from chainlit.lingxi.migrations import run_migrations
from chainlit.lingxi.settings import resolve_db_path


def main() -> None:
    db_path = resolve_db_path()
    print(f"Applying LingXi migrations to: {db_path}")
    run_migrations(db_path)
    print("Database migrations complete.")


if __name__ == "__main__":
    main()
