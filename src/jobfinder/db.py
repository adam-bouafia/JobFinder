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

CREATE TABLE IF NOT EXISTS resume_profile (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path      TEXT NOT NULL,
    raw_text         TEXT NOT NULL,
    skills           TEXT NOT NULL,  -- JSON array
    years_experience REAL,
    education        TEXT NOT NULL,  -- JSON array
    parsed_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name         TEXT NOT NULL,
    title                TEXT NOT NULL,
    location             TEXT,
    url                  TEXT NOT NULL,
    source               TEXT NOT NULL,
    is_open_application  INTEGER NOT NULL DEFAULT 0,
    sponsor_kvk          TEXT,
    sponsor_match_score  REAL,
    fit_score            REAL,
    fetched_at           TEXT NOT NULL,
    UNIQUE(url)
);

CREATE INDEX IF NOT EXISTS idx_sponsors_normalized ON sponsors(name_normalized);
CREATE INDEX IF NOT EXISTS idx_jobs_sponsor_kvk ON jobs(sponsor_kvk);
CREATE INDEX IF NOT EXISTS idx_jobs_fit_score ON jobs(fit_score);
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
