"""Ingest job listings from any source: enrich with sponsor status and an
open-application flag, then store.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..db import cursor
from ..paths import DB_PATH
from ..sponsors.match import load_sponsor_choices, match_against_choices
from .models import JobListing
from .open_applications import is_open_application


def ingest_jobs(listings: list[JobListing], db_path: Path = DB_PATH) -> int:
    """Store listings, enriching each with sponsor-match status and an
    open-application flag.

    Returns the number of new rows inserted - duplicates by URL (a job
    already ingested from a previous run) are silently skipped.
    """
    if not listings:
        return 0

    try:
        choices = load_sponsor_choices(db_path)
    except RuntimeError:
        # Sponsor table not synced yet - still ingest jobs, just unmatched.
        choices = None

    now = datetime.now(UTC).isoformat(timespec="seconds")
    inserted = 0
    with cursor(db_path) as conn:
        for listing in listings:
            sponsor_kvk = None
            sponsor_score = None
            if choices is not None:
                match = match_against_choices(listing.company_name, choices)
                sponsor_score = match.score
                if match.is_sponsor:
                    sponsor_kvk = match.kvk

            result = conn.execute(
                """
                INSERT OR IGNORE INTO jobs
                    (company_name, title, location, url, source,
                     is_open_application, sponsor_kvk, sponsor_match_score, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    listing.company_name,
                    listing.title,
                    listing.location,
                    listing.url,
                    listing.source,
                    int(is_open_application(listing.title)),
                    sponsor_kvk,
                    sponsor_score,
                    now,
                ),
            )
            if result.rowcount:
                inserted += 1
    return inserted


@dataclass(frozen=True)
class StoredJob:
    id: int
    company_name: str
    title: str
    location: str | None
    url: str
    source: str
    is_open_application: bool
    sponsor_kvk: str | None
    fit_score: float | None
    fetched_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> StoredJob:
        return cls(
            id=row["id"],
            company_name=row["company_name"],
            title=row["title"],
            location=row["location"],
            url=row["url"],
            source=row["source"],
            is_open_application=bool(row["is_open_application"]),
            sponsor_kvk=row["sponsor_kvk"],
            fit_score=row["fit_score"],
            fetched_at=row["fetched_at"],
        )


def list_jobs(
    db_path: Path = DB_PATH,
    *,
    sponsors_only: bool = False,
    open_applications_only: bool = False,
    min_fit_score: float | None = None,
    limit: int = 50,
) -> list[StoredJob]:
    """Query stored jobs, ranked by fit score (nulls last)."""
    clauses: list[str] = []
    params: list[object] = []
    if sponsors_only:
        clauses.append("sponsor_kvk IS NOT NULL")
    if open_applications_only:
        clauses.append("is_open_application = 1")
    if min_fit_score is not None:
        clauses.append("fit_score >= ?")
        params.append(min_fit_score)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    with cursor(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM jobs
            {where}
            ORDER BY fit_score IS NULL, fit_score DESC, fetched_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [StoredJob.from_row(row) for row in rows]
