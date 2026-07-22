"""Configuration loaded from explicitly scoped environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime paths and service settings owned by the container."""

    data_dir: Path
    source_dir: Path
    workers: int

    @property
    def database_path(self) -> Path:
        """Return the SQLite database path beneath the application data volume."""
        return self.data_dir / "index" / "ainas.sqlite3"


def load_settings() -> Settings:
    """Load and validate non-sensitive runtime settings from the environment."""
    workers_value = os.environ.get("AI_NAS_WORKERS", "1")
    try:
        workers = int(workers_value)
    except ValueError as error:
        raise ValueError("AI_NAS_WORKERS must be an integer") from error
    if workers < 1:
        raise ValueError("AI_NAS_WORKERS must be at least 1")
    return Settings(
        data_dir=Path(os.environ.get("AI_NAS_DATA_DIR", "/app/data")),
        source_dir=Path(os.environ.get("AI_NAS_SOURCE_DIR", "/source")),
        workers=workers,
    )
