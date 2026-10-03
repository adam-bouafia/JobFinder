"""Tests for jobfinder.db, in particular schema migration.

Every other test fixture in this suite starts from a brand new SQLite
file, where CREATE TABLE IF NOT EXISTS always includes every current
column - that pattern completely missed a real bug (an index on
experience_level in the schema script, which ran before the migration
that adds the column to a *pre-existing* jobs table, raising
OperationalError against the real local database). These tests
deliberately start from a pre-existing table missing a later column.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from jobfinder import db


def test_connect_migrates_a_pre_existing_jobs_table_missing_experience_level(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "pre-existing.db"

    # Simulate the real previous schema - every other jobs column already
    # existed, only experience_level is missing - bypassing db.connect().
    raw_conn = sqlite3.connect(db_path)
    raw_conn.execute(
        """
        CREATE TABLE jobs (
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
        )
        """
    )
    raw_conn.commit()
    raw_conn.close()

    # Must not raise (this is exactly what broke against the real DB).
    conn = db.connect(db_path)
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
        assert "experience_level" in columns
        assert "description" in columns
    finally:
        conn.close()


def test_connect_is_idempotent_across_repeated_opens(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"

    for _ in range(3):
        conn = db.connect(db_path)
        conn.close()

    conn = db.connect(db_path)
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
        assert "experience_level" in columns
    finally:
        conn.close()
