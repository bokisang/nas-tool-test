"""Durable single-worker process for M1 scan jobs."""

from __future__ import annotations

import os
import time

from ainas.config import load_settings
from ainas.db.database import Database
from ainas.m1 import M1Service
from ainas.main import MIGRATIONS_DIR


def main() -> int:
    settings = load_settings()
    database = Database(settings.database_path)
    database.migrate(MIGRATIONS_DIR)
    service = M1Service(database, settings.source_dir)
    service.ensure_root()
    owner = f"worker-{os.getpid()}"
    while True:
        job = service.claim_job(owner)
        if job is None:
            time.sleep(1)
            continue
        service.run_job(job)


if __name__ == "__main__":
    raise SystemExit(main())
