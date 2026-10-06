"""SQLite store — implementation of Contract B (contracts/STORE_SCHEMA.sql)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS commits (
    sha       TEXT PRIMARY KEY,
    ct        INTEGER NOT NULL,
    author    TEXT    NOT NULL,
    subject   TEXT
);
CREATE INDEX IF NOT EXISTS idx_commits_ct     ON commits(ct);
CREATE INDEX IF NOT EXISTS idx_commits_author ON commits(author);

CREATE TABLE IF NOT EXISTS file_stats (
    sha     TEXT NOT NULL,
    path    TEXT NOT NULL,
    added   INTEGER NOT NULL,
    removed INTEGER NOT NULL,
    PRIMARY KEY (sha, path)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_file_stats_path ON file_stats(path);

CREATE TABLE IF NOT EXISTS dir_stats (
    sha     TEXT NOT NULL,
    path    TEXT NOT NULL,
    added   INTEGER NOT NULL,
    removed INTEGER NOT NULL,
    PRIMARY KEY (sha, path)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_dir_stats_path ON dir_stats(path);

CREATE TABLE IF NOT EXISTS author_merges (
    raw       TEXT PRIMARY KEY,
    merged    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_log (
    ts      INTEGER,
    level   TEXT,
    message TEXT
);
"""


def connect(db_path) -> sqlite3.Connection:
    """Open (creating if needed) the store and ensure the schema exists."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -65536")
    return conn


def reset(conn: sqlite3.Connection) -> None:
    """Clear scan-owned tables (author_merges is user data and is preserved)."""
    for table in ("commits", "file_stats", "dir_stats", "scan_log", "meta"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


def set_meta(conn: sqlite3.Connection, pairs: dict) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        [(str(k), str(v)) for k, v in pairs.items()],
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection) -> dict:
    return dict(conn.execute("SELECT key, value FROM meta").fetchall())


def log(conn: sqlite3.Connection, level: str, message: str) -> None:
    import time

    conn.execute("INSERT INTO scan_log(ts, level, message) VALUES (?, ?, ?)",
                 (int(time.time()), level, message))
    conn.commit()
