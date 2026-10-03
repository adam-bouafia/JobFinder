"""Ingest job listings from any source: enrich with sponsor status and an
open-application flag, then store.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..db import cursor
from ..sponsors.match import load_sponsor_choices, match_against_choices
from .experience import classify_experience_level
from .models import JobListing
from .open_applications import is_open_application


def ingest_jobs(listings: list[JobListing], dsn: str | None = None) -> int:
    """Store listings, enriching each with sponsor-match status and an
    open-application flag.

    Returns the number of new rows inserted - duplicates by URL (a job
    already ingested from a previous run) are silently skipped.
    """
    if not listings:
        return 0

    try:
        choices = load_sponsor_choices(dsn)
    except RuntimeError:
        # Sponsor table not synced yet - still ingest jobs, just unmatched.
        choices = None

    now = datetime.now(UTC)
    inserted = 0
    with cursor(dsn) as conn:
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
                INSERT INTO jobs
                    (company_name, title, location, url, source,
                     is_open_application, sponsor_kvk, sponsor_match_score,
                     experience_level, description, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING
                """,
                (
                    listing.company_name,
                    listing.title,
                    listing.location,
                    listing.url,
                    listing.source,
                    is_open_application(listing.title),
                    sponsor_kvk,
                    sponsor_score,
                    classify_experience_level(listing.title),
                    listing.description,
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
    experience_level: str | None
    description: str | None
    fetched_at: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> StoredJob:
        return cls(
            id=row["id"],
            company_name=row["company_name"],
            title=row["title"],
            location=row["location"],
            url=row["url"],
            source=row["source"],
            is_open_application=row["is_open_application"],
            sponsor_kvk=row["sponsor_kvk"],
            fit_score=row["fit_score"],
            experience_level=row["experience_level"],
            description=row["description"],
            fetched_at=row["fetched_at"].isoformat(timespec="seconds"),
        )


def _build_where(
    query: str | None,
    sponsors_only: bool,
    open_applications_only: bool,
    experience_level: str | None,
    min_fit_score: float | None,
    city: str | None,
) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []
    if query:
        clauses.append("(title ILIKE %s OR company_name ILIKE %s)")
        like_query = f"%{query}%"
        params.extend([like_query, like_query])
    if city:
        clauses.append("location ILIKE %s")
        params.append(f"%{city}%")
    if sponsors_only:
        clauses.append("sponsor_kvk IS NOT NULL")
    if open_applications_only:
        clauses.append("is_open_application = TRUE")
    if experience_level:
        clauses.append("experience_level = %s")
        params.append(experience_level)
    if min_fit_score is not None:
        clauses.append("fit_score >= %s")
        params.append(min_fit_score)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def list_jobs(
    dsn: str | None = None,
    *,
    query: str | None = None,
    city: str | None = None,
    sponsors_only: bool = False,
    open_applications_only: bool = False,
    experience_level: str | None = None,
    min_fit_score: float | None = None,
    limit: int = 50,
) -> list[StoredJob]:
    """Query stored jobs, ranked by fit score (nulls last).

    `query` is a plain substring match against title or company name, and
    `city` against location - a job search box, not the fuzzy sponsor
    matching used elsewhere.
    """
    where, params = _build_where(
        query, sponsors_only, open_applications_only, experience_level, min_fit_score, city
    )
    params = [*params, limit]

    with cursor(dsn) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM jobs
            {where}
            ORDER BY fit_score IS NULL, fit_score DESC, fetched_at DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
    return [StoredJob.from_row(row) for row in rows]


def count_jobs(
    dsn: str | None = None,
    *,
    query: str | None = None,
    city: str | None = None,
    sponsors_only: bool = False,
    open_applications_only: bool = False,
    experience_level: str | None = None,
    min_fit_score: float | None = None,
) -> int:
    """Total matching rows, ignoring `list_jobs`'s display limit - so the
    UI can show "showing 100 of 240" instead of a count capped at the page
    size."""
    where, params = _build_where(
        query, sponsors_only, open_applications_only, experience_level, min_fit_score, city
    )
    with cursor(dsn) as conn:
        row = conn.execute(f"SELECT COUNT(*) AS c FROM jobs {where}", params).fetchone()
    assert row is not None  # COUNT(*) always returns exactly one row
    return int(row["c"])
