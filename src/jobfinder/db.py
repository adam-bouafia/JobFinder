"""PostgreSQL storage for JobFinder."""

from __future__ import annotations

import atexit
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DictConnection = psycopg.Connection[dict[str, Any]]

SCHEMA = """
CREATE TABLE IF NOT EXISTS sponsors (
    kvk             TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS resume_profile (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_path      TEXT NOT NULL,
    raw_text         TEXT NOT NULL,
    skills           TEXT[] NOT NULL,
    years_experience REAL,
    education        TEXT[] NOT NULL,
    parsed_at        TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_name         TEXT NOT NULL,
    title                TEXT NOT NULL,
    location             TEXT,
    url                  TEXT NOT NULL,
    source               TEXT NOT NULL,
    is_open_application  BOOLEAN NOT NULL DEFAULT FALSE,
    sponsor_kvk          TEXT,
    sponsor_match_score  REAL,
    fit_score            REAL,
    experience_level     TEXT,
    description          TEXT,
    fetched_at           TIMESTAMPTZ NOT NULL,
    UNIQUE(url)
);

CREATE INDEX IF NOT EXISTS idx_sponsors_normalized ON sponsors(name_normalized);
CREATE INDEX IF NOT EXISTS idx_jobs_sponsor_kvk ON jobs(sponsor_kvk);
CREATE INDEX IF NOT EXISTS idx_jobs_fit_score ON jobs(fit_score);
"""


def _migrate(conn: DictConnection) -> None:
    """Add columns (and their indexes) introduced after a table's initial
    CREATE TABLE.

    CREATE TABLE IF NOT EXISTS doesn't retroactively add new columns to an
    already-existing table, so a real schema change (like adding
    experience_level to an existing jobs table with live data in it) needs
    an explicit, idempotent ALTER TABLE here - and the column's index has
    to live here too, not in SCHEMA: on a pre-existing database, running
    SCHEMA runs before this function, so an index on a column that doesn't
    exist yet would fail - a brand new database gets every column straight
    from CREATE TABLE, so this ordering only matters for upgrades.
    """
    existing_columns = {
        row["column_name"]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs'"
        ).fetchall()
    }
    if "experience_level" not in existing_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN experience_level TEXT")
    if "description" not in existing_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN description TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_experience_level ON jobs(experience_level)")


_pool: ConnectionPool[DictConnection] | None = None


def _env_dsn() -> str:
    """Read DATABASE_URL lazily (at call time, not import time).

    Why not a module-level constant: this module is imported transitively
    before `cli.py` calls `load_dotenv()` (it's pulled in by several of the
    `from .jobs... import ...` lines above that call), so reading the env
    var at import time would miss a value that only `.env` provides -
    exactly the kind of ordering bug that's easy to introduce silently.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Set it in .env for local dev, or as a "
            "Modal Secret for deployment."
        )
    return dsn


def _get_pool() -> ConnectionPool[DictConnection]:
    global _pool
    if _pool is None:
        # kwargs={"row_factory": dict_row} is what actually makes every
        # connection from this pool return dict rows at runtime; psycopg's
        # own ConnectionPool type doesn't thread that through to its generic
        # parameter, so the cast just tells mypy what's already true.
        _pool = cast(
            "ConnectionPool[DictConnection]",
            ConnectionPool(
                _env_dsn(), min_size=1, max_size=5, open=True, kwargs={"row_factory": dict_row}
            ),
        )
        # Without this, a short-lived process (every CLI command) hits
        # PythonFinalizationError on exit: the pool's worker thread can't be
        # joined once interpreter shutdown has already started tearing down
        # threading internals. atexit runs earlier, while that's still safe.
        atexit.register(_pool.close)
    return _pool


@contextmanager
def cursor(dsn: str | None = None) -> Iterator[DictConnection]:
    """Yield a connection, committing on success and always closing/
    returning it.

    Same call-site contract the SQLite version had: `with cursor() as conn:
    conn.execute(...)`. With no `dsn` (the normal case - CLI, web app),
    this borrows from a lazily-created pool against DATABASE_URL: a single
    page load can make several of these calls (sponsor stats, job search,
    resume lookup), and Neon's serverless cold-connect latency would
    otherwise land on every one of them. Tests pass an explicit `dsn`
    (their own throwaway schema) and get a plain direct connection instead
    - no pooling needed there, and it keeps each test's connection target
    fully explicit rather than depending on process-wide pool state.
    """
    if dsn is None:
        with _get_pool().connection() as conn:
            conn.execute(SCHEMA)
            _migrate(conn)
            yield conn
    else:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            conn.execute(SCHEMA)
            _migrate(conn)
            yield conn


@dataclass(frozen=True)
class SponsorStats:
    count: int
    synced_at: str | None


def sponsor_stats(dsn: str | None = None) -> SponsorStats:
    """Row count and last-sync timestamp, for status display in the CLI/UI."""
    with cursor(dsn) as conn:
        count_row = conn.execute("SELECT COUNT(*) AS c FROM sponsors").fetchone()
        assert count_row is not None  # COUNT(*) always returns exactly one row
        row = conn.execute("SELECT value FROM meta WHERE key = 'ind_synced_at'").fetchone()
    return SponsorStats(count=count_row["c"], synced_at=row["value"] if row else None)
