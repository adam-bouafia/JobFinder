"""Tests for jobfinder.db, in particular schema migration.

Every other test fixture in this suite starts from a brand new schema,
where CREATE TABLE IF NOT EXISTS always includes every current column -
that pattern completely missed a real bug (an index on experience_level
in the schema script, which ran before the migration that adds the
column to a *pre-existing* jobs table, raising an error against the real
local database). These tests deliberately start from a pre-existing
table missing a later column.
"""

from __future__ import annotations

import psycopg

from jobfinder import db


def test_connect_migrates_a_pre_existing_jobs_table_missing_experience_level(dsn: str) -> None:
    # Simulate the real previous schema - every other jobs column already
    # existed, only experience_level/description are missing - bypassing
    # db.cursor() so nothing auto-applies the current SCHEMA first.
    with psycopg.connect(dsn) as raw_conn:
        raw_conn.execute(
            """
            CREATE TABLE jobs (
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
                fetched_at           TIMESTAMPTZ NOT NULL,
                UNIQUE(url)
            )
            """
        )

    # Must not raise (this is exactly what broke against the real DB).
    with db.cursor(dsn) as conn:
        columns = {
            row["column_name"]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs'"
            ).fetchall()
        }
    assert "experience_level" in columns
    assert "description" in columns


def test_cursor_is_idempotent_across_repeated_opens(dsn: str) -> None:
    for _ in range(3):
        with db.cursor(dsn):
            pass

    with db.cursor(dsn) as conn:
        columns = {
            row["column_name"]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs'"
            ).fetchall()
        }
    assert "experience_level" in columns
