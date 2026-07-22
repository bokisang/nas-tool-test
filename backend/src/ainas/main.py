"""FastAPI application serving the M0 health API and compiled web assets."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ainas.config import Settings, load_settings
from ainas.db.database import Database
from ainas.m1 import DEFAULT_ROOT_ID, M1Service

PACKAGE_DIR = Path(__file__).resolve().parent
MIGRATIONS_DIR = PACKAGE_DIR / "migrations"
STATIC_DIR = Path("/app/static")


def create_app(settings: Settings | None = None, static_dir: Path = STATIC_DIR) -> FastAPI:
    """Create an application with a database initialized during startup."""
    runtime_settings = settings or load_settings()
    database = Database(runtime_settings.database_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        database.migrate(MIGRATIONS_DIR)
        yield

    app = FastAPI(title="AI NAS Search", version="0.1.0", lifespan=lifespan)
    app.state.database = database
    app.state.settings = runtime_settings
    app.state.m1 = M1Service(database, runtime_settings.source_dir)

    @app.get("/healthz", tags=["system"])
    def healthz() -> dict[str, str]:
        if not database.is_healthy():
            raise HTTPException(status_code=503, detail="database unavailable")
        return {"status": "ok"}

    @app.get("/api/v1/status", tags=["system"])
    def status() -> dict[str, str | int]:
        return {"status": "ready", "version": app.version, "workers": runtime_settings.workers}

    @app.get("/api/v1/roots", tags=["roots"])
    def roots() -> list[dict[str, object]]:
        service = cast(M1Service, app.state.m1)
        service.ensure_root()
        return service.roots()

    @app.post("/api/v1/roots/{root_id}/scan", status_code=202, tags=["roots"])
    def queue_scan(root_id: str) -> dict[str, str]:
        service = cast(M1Service, app.state.m1)
        try:
            return {"job_id": service.enqueue_scan(root_id)}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="root not found") from error

    @app.get("/api/v1/entries", tags=["entries"])
    def entries(
        root_id: str = DEFAULT_ROOT_ID,
        parent_id: int | None = None,
        cursor: int | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        service = cast(M1Service, app.state.m1)
        try:
            return service.list_entries(root_id, parent_id, cursor, limit)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="entry or root not found") from error

    @app.get("/api/v1/entries/{entry_id}", tags=["entries"])
    def entry(entry_id: int) -> dict[str, object]:
        service = cast(M1Service, app.state.m1)
        try:
            return service.entry(entry_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="entry not found") from error

    @app.get("/api/v1/jobs", tags=["jobs"])
    def jobs() -> list[dict[str, object]]:
        service = cast(M1Service, app.state.m1)
        return service.jobs()

    if static_dir.is_dir():
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
