"""SQLite storage for JobFinder."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .paths import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS sponsors (
    kvk             TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    fetched_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_sponsors_normalized ON sponsors(name_normalized);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open a connection with the schema applied and WAL mode on.

    Why WAL: lets a sync run and a read happen without blocking each other,
    the only concurrency case this single-user tool has.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def cursor(path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    """Yield a connection, committing on success and always closing."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@dataclass(frozen=True)
class SponsorStats:
    count: int
    synced_at: str | None


def sponsor_stats(path: Path = DB_PATH) -> SponsorStats:
    """Row count and last-sync timestamp, for status display in the CLI/UI."""
    with cursor(path) as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM sponsors").fetchone()["c"]
        row = conn.execute("SELECT value FROM meta WHERE key = 'ind_synced_at'").fetchone()
    return SponsorStats(count=count, synced_at=row["value"] if row else None)
