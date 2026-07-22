"""SQLite connection and idempotent schema migration support."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    """Own the application-local SQLite database and its safety pragmas."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @property
    def database_path(self) -> Path:
        """Return the configured path without exposing connection internals."""
        return self._database_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured SQLite connection and always close it."""
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self, migrations_dir: Path) -> None:
        """Apply each numbered SQL migration exactly once in a transaction."""
        migration_files = sorted(migrations_dir.glob("*.sql"))
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            applied = {
                row[0] for row in connection.execute("SELECT version FROM schema_migrations")
            }
            for migration_path in migration_files:
                version = migration_path.name
                if version in applied:
                    continue
                migration_sql = migration_path.read_text(encoding="utf-8")
                connection.executescript(
                    "BEGIN IMMEDIATE;\n"
                    f"{migration_sql}\n"
                    f"INSERT INTO schema_migrations(version) VALUES ('{version}');\n"
                    "COMMIT;"
                )

    def is_healthy(self) -> bool:
        """Return whether SQLite accepts a simple query after migration."""
        try:
            with self.connect() as connection:
                result = connection.execute("SELECT 1").fetchone()
                return result is not None and result[0] == 1
        except sqlite3.Error:
            return False
