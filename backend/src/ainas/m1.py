"""M1 repositories, durable scan jobs, and safe streaming filesystem scanner."""
# ruff: noqa: E501

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from ainas.db.database import Database

DEFAULT_ROOT_ID = "default"


@dataclass(frozen=True, slots=True)
class ScanResult:
    run_id: str
    state: str
    entries_seen: int


class M1Service:
    """Own M1 metadata while never accepting a host path from HTTP input."""

    def __init__(self, database: Database, source_dir: Path) -> None:
        self.database, self.source_dir = database, source_dir

    def ensure_root(self) -> None:
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO roots(id, source_path) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET source_path=excluded.source_path, updated_at=CURRENT_TIMESTAMP",
                (DEFAULT_ROOT_ID, str(self.source_dir)),
            )

    def roots(self) -> list[dict[str, object]]:
        with self.database.connect() as conn:
            return [
                dict(row)
                for row in self._rows(
                    conn.execute(
                        "SELECT id,status,current_generation,last_error,updated_at FROM roots ORDER BY id"
                    )
                )
            ]

    def enqueue_scan(self, root_id: str) -> str:
        self._require_root(root_id)
        job_id, run_id = str(uuid.uuid4()), str(uuid.uuid4())
        with self.database.connect() as conn:
            generation = conn.execute(
                "SELECT current_generation + 1 FROM roots WHERE id=?", (root_id,)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO scan_runs(id,root_id,generation,status) VALUES (?,?,?,'queued')",
                (run_id, root_id, generation),
            )
            conn.execute(
                "INSERT INTO jobs(id,root_id,kind,state,payload) VALUES (?,?,'scan','queued',?)",
                (job_id, root_id, json.dumps({"run_id": run_id})),
            )
        return job_id

    def claim_job(self, owner: str) -> dict[str, object] | None:
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT id FROM jobs WHERE (state IN ('queued','retry') OR (state='running' AND lease_until < CURRENT_TIMESTAMP)) ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE jobs SET state='running', lease_owner=?, lease_until=datetime('now','+60 seconds'), attempts=attempts+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (owner, row[0]),
            )
            claimed = conn.execute("SELECT * FROM jobs WHERE id=?", (row[0],)).fetchone()
            return dict(claimed)

    def run_job(self, job: dict[str, object]) -> None:
        try:
            payload = json.loads(str(job["payload"]))
            self.scan(str(job["root_id"]), str(payload["run_id"]))
            with self.database.connect() as conn:
                conn.execute(
                    "UPDATE jobs SET state='completed', lease_owner=NULL, lease_until=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (job["id"],),
                )
        except OSError as error:
            with self.database.connect() as conn:
                conn.execute(
                    "UPDATE jobs SET state='retry', error_code=?, lease_owner=NULL, lease_until=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (type(error).__name__, job["id"]),
                )

    def scan(self, root_id: str, run_id: str) -> ScanResult:
        self._require_root(root_id)
        root = self.source_dir.resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError(root)
        root_stat = root.stat()
        with self.database.connect() as conn:
            run = conn.execute(
                "SELECT generation FROM scan_runs WHERE id=? AND root_id=?", (run_id, root_id)
            ).fetchone()
            if run is None:
                raise KeyError(run_id)
            generation = int(run[0])
            conn.execute(
                "UPDATE scan_runs SET status='running', error_code=NULL WHERE id=?", (run_id,)
            )
            conn.execute(
                "UPDATE roots SET status='scanning', last_error=NULL WHERE id=?", (root_id,)
            )
        count = 0
        stack: list[Path] = [root]
        while stack:
            directory = stack.pop()
            with os.scandir(directory) as children:
                for child in children:
                    if child.is_symlink():
                        continue
                    stat = child.stat(follow_symlinks=False)
                    if os.name != "nt" and stat.st_dev != root_stat.st_dev:
                        continue
                    relative = Path(child.path).relative_to(root).as_posix()
                    if not relative or any(
                        part in {"@Recycle", ".snapshot", ".git", "node_modules"}
                        for part in relative.split("/")
                    ):
                        continue
                    is_dir = child.is_dir(follow_symlinks=False)
                    self._upsert(
                        root_id,
                        relative,
                        child.name,
                        "directory" if is_dir else "file",
                        stat,
                        generation,
                    )
                    count += 1
                    if is_dir:
                        stack.append(Path(child.path))
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE entries SET state=CASE WHEN missing_confirmations >= 1 THEN 'tombstone' ELSE 'missing' END, missing_confirmations=missing_confirmations+1 WHERE root_id=? AND generation<>? AND state='active'",
                (root_id, generation),
            )
            conn.execute(
                "UPDATE roots SET status='healthy',current_generation=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (generation, root_id),
            )
            conn.execute(
                "UPDATE scan_runs SET status='completed',entries_seen=?,completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (count, run_id),
            )
        return ScanResult(run_id, "completed", count)

    def list_entries(
        self, root_id: str, parent_id: int | None, cursor: int | None, limit: int
    ) -> dict[str, object]:
        self._require_root(root_id)
        limit = min(max(limit, 1), 200)
        with self.database.connect() as conn:
            parent = "" if parent_id is None else self._entry_path(conn, parent_id, root_id)
            rows = list(
                self._rows(
                    conn.execute(
                        "SELECT id,name,kind,size_bytes,mtime_ns,parent_path FROM entries WHERE root_id=? AND parent_path=? AND state='active' AND id>? ORDER BY id LIMIT ?",
                        (root_id, parent, cursor or 0, limit + 1),
                    )
                )
            )
        has_more = len(rows) > limit
        items = [dict(row) for row in rows[:limit]]
        return {"items": items, "next_cursor": items[-1]["id"] if has_more else None}

    def entry(self, entry_id: int) -> dict[str, object]:
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT id,root_id,relative_path,name,kind,size_bytes,mtime_ns,parent_path FROM entries WHERE id=? AND state='active'",
                (entry_id,),
            ).fetchone()
            if row is None:
                raise KeyError(entry_id)
            return dict(row)

    def jobs(self) -> list[dict[str, object]]:
        with self.database.connect() as conn:
            return [
                dict(row)
                for row in self._rows(
                    conn.execute(
                        "SELECT id,root_id,kind,state,attempts,error_code,created_at,updated_at FROM jobs ORDER BY created_at DESC"
                    )
                )
            ]

    @staticmethod
    def _rows(cursor: sqlite3.Cursor) -> Iterator[sqlite3.Row]:
        yield from cursor.fetchall()

    def _require_root(self, root_id: str) -> None:
        if root_id != DEFAULT_ROOT_ID:
            raise KeyError(root_id)

    def _entry_path(self, conn: sqlite3.Connection, entry_id: int, root_id: str) -> str:
        row = conn.execute(
            "SELECT relative_path FROM entries WHERE id=? AND root_id=? AND kind='directory' AND state='active'",
            (entry_id, root_id),
        ).fetchone()
        if row is None:
            raise KeyError(entry_id)
        return str(row[0])

    def _upsert(
        self,
        root_id: str,
        relative: str,
        name: str,
        kind: str,
        stat: os.stat_result,
        generation: int,
    ) -> None:
        parent = relative.rsplit("/", 1)[0] if "/" in relative else ""
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO entries(root_id,relative_path,parent_path,name,kind,size_bytes,mtime_ns,device,inode,generation,state,missing_confirmations) VALUES (?,?,?,?,?,?,?,?,?,?, 'active',0) ON CONFLICT(root_id,relative_path) DO UPDATE SET parent_path=excluded.parent_path,name=excluded.name,kind=excluded.kind,size_bytes=excluded.size_bytes,mtime_ns=excluded.mtime_ns,device=excluded.device,inode=excluded.inode,generation=excluded.generation,state='active',missing_confirmations=0",
                (
                    root_id,
                    relative,
                    parent,
                    name,
                    kind,
                    stat.st_size,
                    stat.st_mtime_ns,
                    stat.st_dev,
                    stat.st_ino,
                    generation,
                ),
            )
