"""Tests for jobfinder.jobs.ingest."""

from __future__ import annotations

from pathlib import Path

import pytest

from jobfinder import db
from jobfinder.jobs.ingest import ingest_jobs, list_jobs
from jobfinder.jobs.models import JobListing
from jobfinder.sponsors.normalize import normalize


@pytest.fixture
def seeded_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    with db.cursor(db_path) as conn:
        conn.execute(
            "INSERT INTO sponsors (kvk, name, name_normalized, fetched_at) VALUES (?, ?, ?, ?)",
            ("31047344", "Booking.com B.V.", normalize("Booking.com B.V."), "2026-10-01T00:00:00"),
        )
    return db_path


def test_ingest_jobs_enriches_with_sponsor_match(seeded_db: Path) -> None:
    listings = [
        JobListing(
            company_name="Booking.com",
            title="Backend Engineer",
            location="Amsterdam, Netherlands",
            url="https://example.com/job/1",
            source="greenhouse",
        )
    ]

    inserted = ingest_jobs(listings, db_path=seeded_db)

    assert inserted == 1
    jobs = list_jobs(db_path=seeded_db)
    assert len(jobs) == 1
    assert jobs[0].sponsor_kvk == "31047344"


def test_ingest_jobs_leaves_unmatched_companies_unmatched(seeded_db: Path) -> None:
    listings = [
        JobListing(
            company_name="Totally Unrelated Bakery XYZ",
            title="Baker",
            location=None,
            url="https://example.com/job/2",
            source="greenhouse",
        )
    ]

    ingest_jobs(listings, db_path=seeded_db)

    jobs = list_jobs(db_path=seeded_db)
    assert jobs[0].sponsor_kvk is None


def test_ingest_jobs_flags_open_applications(seeded_db: Path) -> None:
    listings = [
        JobListing(
            company_name="Booking.com",
            title="General Application",
            location=None,
            url="https://example.com/job/3",
            source="greenhouse",
        )
    ]

    ingest_jobs(listings, db_path=seeded_db)

    jobs = list_jobs(db_path=seeded_db)
    assert jobs[0].is_open_application is True


def test_ingest_jobs_deduplicates_by_url(seeded_db: Path) -> None:
    listing = JobListing(
        company_name="Booking.com",
        title="Backend Engineer",
        location=None,
        url="https://example.com/job/1",
        source="greenhouse",
    )

    first = ingest_jobs([listing], db_path=seeded_db)
    second = ingest_jobs([listing], db_path=seeded_db)

    assert first == 1
    assert second == 0
    assert len(list_jobs(db_path=seeded_db)) == 1


def test_ingest_jobs_works_without_synced_sponsors(tmp_path: Path) -> None:
    empty_db = tmp_path / "empty.db"
    with db.cursor(empty_db):
        pass

    listing = JobListing(
        company_name="Booking.com",
        title="Backend Engineer",
        location=None,
        url="https://example.com/job/1",
        source="greenhouse",
    )

    inserted = ingest_jobs([listing], db_path=empty_db)

    assert inserted == 1
    jobs = list_jobs(db_path=empty_db)
    assert jobs[0].sponsor_kvk is None


def test_list_jobs_filters_by_sponsors_only(seeded_db: Path) -> None:
    ingest_jobs(
        [
            JobListing("Booking.com", "A", None, "https://x/1", "greenhouse"),
            JobListing("Unrelated Co", "B", None, "https://x/2", "greenhouse"),
        ],
        db_path=seeded_db,
    )

    jobs = list_jobs(db_path=seeded_db, sponsors_only=True)

    assert len(jobs) == 1
    assert jobs[0].company_name == "Booking.com"
