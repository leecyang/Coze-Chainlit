"""Versioned SQLite migration runner for LingXi runtime tables."""

import hashlib
import sqlite3
from pathlib import Path
from typing import Iterable, Tuple


def _iter_migration_files(migrations_dir: Path) -> Iterable[Tuple[str, Path]]:
    for path in sorted(migrations_dir.glob("*.sql")):
        version = path.name.split("_", 1)[0]
        if version.isdigit():
            yield version, path


def run_migrations(db_path: str, migrations_dir: Path | None = None) -> None:
    """Apply pending SQL migrations exactly once.

    The runner is intentionally synchronous because it runs during process
    startup before the app starts serving requests.
    """
    db_file = Path(db_path)
    if db_file.parent:
        db_file.parent.mkdir(parents=True, exist_ok=True)
    if migrations_dir is None:
        migrations_dir = Path(__file__).resolve().parents[2] / "migrations"

    conn = sqlite3.connect(str(db_file), timeout=30)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        applied = {
            row[0]: row[1]
            for row in conn.execute("SELECT version, checksum FROM schema_migrations")
        }

        for version, path in _iter_migration_files(migrations_dir):
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(
                        f"Migration {path.name} checksum changed after it was applied"
                    )
                continue
            print(f"[Migrations] Applying {path.name}")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                (version, checksum),
            )
            conn.commit()
    finally:
        conn.close()
