"""Container health-check entry point."""

from __future__ import annotations

from ainas.config import load_settings
from ainas.db.database import Database
from ainas.main import MIGRATIONS_DIR


def main() -> int:
    """Initialize the schema and return a process status for Docker."""
    settings = load_settings()
    database = Database(settings.database_path)
    database.migrate(MIGRATIONS_DIR)
    return 0 if database.is_healthy() else 1


if __name__ == "__main__":
    raise SystemExit(main())
