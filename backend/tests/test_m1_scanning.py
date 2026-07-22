from pathlib import Path

from ainas.db.database import Database
from ainas.m1 import DEFAULT_ROOT_ID, M1Service
from ainas.main import MIGRATIONS_DIR


def _service(tmp_path: Path) -> tuple[M1Service, Path]:
    source = tmp_path / "source"
    source.mkdir()
    database = Database(tmp_path / "data" / "index" / "ainas.sqlite3")
    database.migrate(MIGRATIONS_DIR)
    service = M1Service(database, source)
    service.ensure_root()
    return service, source


def test_worker_claim_scans_streamed_entries_and_persists_result(tmp_path: Path) -> None:
    service, source = _service(tmp_path)
    (source / "notes").mkdir()
    (source / "notes" / "plan.txt").write_text("local only", encoding="utf-8")

    service.enqueue_scan(DEFAULT_ROOT_ID)
    job = service.claim_job("test-worker")

    assert job is not None
    service.run_job(job)
    top_level = service.list_entries(DEFAULT_ROOT_ID, None, None, 10)
    directory = top_level["items"][0]
    children = service.list_entries(DEFAULT_ROOT_ID, int(directory["id"]), None, 10)

    assert directory["name"] == "notes"
    assert children["items"][0]["name"] == "plan.txt"
    assert next(item for item in service.jobs() if item["id"] == job["id"])["state"] == "completed"


def test_offline_source_retries_without_tombstoning_index(tmp_path: Path) -> None:
    service, source = _service(tmp_path)
    (source / "keep.txt").write_text("safe", encoding="utf-8")
    service.enqueue_scan(DEFAULT_ROOT_ID)
    first_job = service.claim_job("test-worker")
    assert first_job is not None
    service.run_job(first_job)
    source.rename(tmp_path / "offline-source")

    service.enqueue_scan(DEFAULT_ROOT_ID)
    retry_job = service.claim_job("test-worker")
    assert retry_job is not None
    service.run_job(retry_job)

    retry_state = next(item for item in service.jobs() if item["id"] == retry_job["id"])[
        "state"
    ]
    assert retry_state == "retry"
    assert service.list_entries(DEFAULT_ROOT_ID, None, None, 10)["items"][0]["name"] == "keep.txt"
