CREATE TABLE roots (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unknown',
    current_generation INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE scan_runs (
    id TEXT PRIMARY KEY,
    root_id TEXT NOT NULL REFERENCES roots(id),
    generation INTEGER NOT NULL,
    status TEXT NOT NULL,
    entries_seen INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);
CREATE TABLE entries (
    id INTEGER PRIMARY KEY,
    root_id TEXT NOT NULL REFERENCES roots(id),
    relative_path TEXT NOT NULL,
    parent_path TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('file', 'directory')),
    size_bytes INTEGER NOT NULL DEFAULT 0,
    mtime_ns INTEGER NOT NULL,
    device INTEGER NOT NULL,
    inode INTEGER NOT NULL,
    generation INTEGER NOT NULL,
    missing_confirmations INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active', 'missing', 'tombstone')),
    UNIQUE(root_id, relative_path)
);
CREATE INDEX entries_root_parent_name ON entries(root_id, parent_path, state, name, id);
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    root_id TEXT NOT NULL REFERENCES roots(id),
    kind TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('queued', 'running', 'retry', 'completed', 'failed', 'cancelled')),
    payload TEXT NOT NULL,
    lease_owner TEXT,
    lease_until TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX jobs_claim ON jobs(state, lease_until, created_at);
