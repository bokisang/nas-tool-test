from pathlib import Path

from fastapi.testclient import TestClient

from ainas.config import Settings
from ainas.main import create_app


def test_health_check_initializes_persistent_database(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", source_dir=tmp_path / "source", workers=1)
    app = create_app(settings=settings, static_dir=tmp_path / "static")
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert settings.database_path.exists()


def test_status_exposes_no_source_path(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        source_dir=tmp_path / "private-source",
        workers=1,
    )
    app = create_app(settings=settings, static_dir=tmp_path / "static")
    with TestClient(app) as client:
        response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "version": "0.1.0", "workers": 1}
