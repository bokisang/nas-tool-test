import sqlite3
from pathlib import Path

from ainas.db.database import Database
from ainas.main import MIGRATIONS_DIR


def test_migration_is_idempotent_and_records_version(tmp_path: Path) -> None:
    database = Database(tmp_path / "data" / "index" / "ainas.sqlite3")
    database.migrate(MIGRATIONS_DIR)
    database.migrate(MIGRATIONS_DIR)
    with sqlite3.connect(database.database_path) as connection:
        migrations = connection.execute("SELECT version FROM schema_migrations").fetchall()
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()
    assert migrations == [("0001_initial.sql",), ("0002_m1_scanning.sql",)]
    assert journal_mode == ("wal",)
