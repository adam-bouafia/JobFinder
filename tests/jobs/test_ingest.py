"""Tests for jobfinder.jobs.ingest."""

from __future__ import annotations

import pytest

from jobfinder import db
from jobfinder.jobs.ingest import distinct_cities, ingest_jobs, list_jobs, reindex_all_jobs
from jobfinder.jobs.models import JobListing
from jobfinder.search import meilisearch_client
from jobfinder.sponsors.normalize import normalize


@pytest.fixture
def seeded_db(dsn: str) -> str:
    with db.cursor(dsn) as conn:
        conn.execute(
            "INSERT INTO sponsors (kvk, name, name_normalized, fetched_at) VALUES (%s, %s, %s, %s)",
            ("31047344", "Booking.com B.V.", normalize("Booking.com B.V."), "2026-10-01T00:00:00"),
        )
    return dsn


def test_ingest_jobs_enriches_with_sponsor_match(seeded_db: str) -> None:
    listings = [
        JobListing(
            company_name="Booking.com",
            title="Backend Engineer",
            location="Amsterdam, Netherlands",
            url="https://example.com/job/1",
            source="greenhouse",
        )
    ]

    inserted = ingest_jobs(listings, dsn=seeded_db)

    assert inserted == 1
    jobs = list_jobs(dsn=seeded_db)
    assert len(jobs) == 1
    assert jobs[0].sponsor_kvk == "31047344"


def test_ingest_jobs_leaves_unmatched_companies_unmatched(seeded_db: str) -> None:
    listings = [
        JobListing(
            company_name="Totally Unrelated Bakery XYZ",
            title="Baker",
            location=None,
            url="https://example.com/job/2",
            source="greenhouse",
        )
    ]

    ingest_jobs(listings, dsn=seeded_db)

    jobs = list_jobs(dsn=seeded_db)
    assert jobs[0].sponsor_kvk is None


def test_ingest_jobs_flags_open_applications(seeded_db: str) -> None:
    listings = [
        JobListing(
            company_name="Booking.com",
            title="General Application",
            location=None,
            url="https://example.com/job/3",
            source="greenhouse",
        )
    ]

    ingest_jobs(listings, dsn=seeded_db)

    jobs = list_jobs(dsn=seeded_db)
    assert jobs[0].is_open_application is True


def test_ingest_jobs_deduplicates_by_url(seeded_db: str) -> None:
    listing = JobListing(
        company_name="Booking.com",
        title="Backend Engineer",
        location=None,
        url="https://example.com/job/1",
        source="greenhouse",
    )

    first = ingest_jobs([listing], dsn=seeded_db)
    second = ingest_jobs([listing], dsn=seeded_db)

    assert first == 1
    assert second == 0
    assert len(list_jobs(dsn=seeded_db)) == 1


def test_ingest_jobs_works_without_synced_sponsors(dsn: str) -> None:
    with db.cursor(dsn):
        pass

    listing = JobListing(
        company_name="Booking.com",
        title="Backend Engineer",
        location=None,
        url="https://example.com/job/1",
        source="greenhouse",
    )

    inserted = ingest_jobs([listing], dsn=dsn)

    assert inserted == 1
    jobs = list_jobs(dsn=dsn)
    assert jobs[0].sponsor_kvk is None


def test_list_jobs_filters_by_sponsors_only(seeded_db: str) -> None:
    ingest_jobs(
        [
            JobListing("Booking.com", "A", None, "https://x/1", "greenhouse"),
            JobListing("Unrelated Co", "B", None, "https://x/2", "greenhouse"),
        ],
        dsn=seeded_db,
    )

    jobs = list_jobs(dsn=seeded_db, sponsors_only=True)

    assert len(jobs) == 1
    assert jobs[0].company_name == "Booking.com"


def test_ingest_jobs_classifies_experience_level(seeded_db: str) -> None:
    ingest_jobs(
        [
            JobListing("Booking.com", "Junior Backend Engineer", None, "https://x/1", "test"),
            JobListing("Booking.com", "Senior Backend Engineer", None, "https://x/2", "test"),
            JobListing("Booking.com", "Backend Engineer", None, "https://x/3", "test"),
        ],
        dsn=seeded_db,
    )

    jobs = {job.url: job for job in list_jobs(dsn=seeded_db, limit=10)}

    assert jobs["https://x/1"].experience_level == "junior"
    assert jobs["https://x/2"].experience_level == "senior"
    assert jobs["https://x/3"].experience_level == "mid"


def test_list_jobs_filters_by_experience_level(seeded_db: str) -> None:
    ingest_jobs(
        [
            JobListing("Booking.com", "Junior Backend Engineer", None, "https://x/1", "test"),
            JobListing("Booking.com", "Senior Backend Engineer", None, "https://x/2", "test"),
        ],
        dsn=seeded_db,
    )

    jobs = list_jobs(dsn=seeded_db, experience_level="junior")

    assert len(jobs) == 1
    assert jobs[0].title == "Junior Backend Engineer"


def test_list_jobs_filters_by_free_text_query_on_title(seeded_db: str) -> None:
    ingest_jobs(
        [
            JobListing("Booking.com", "Platform Engineer", None, "https://x/1", "test"),
            JobListing("Booking.com", "Data Analyst", None, "https://x/2", "test"),
        ],
        dsn=seeded_db,
    )

    jobs = list_jobs(dsn=seeded_db, query="platform")

    assert len(jobs) == 1
    assert jobs[0].title == "Platform Engineer"


def test_list_jobs_filters_by_free_text_query_on_company_name(seeded_db: str) -> None:
    ingest_jobs(
        [
            JobListing("Booking.com", "Engineer", None, "https://x/1", "test"),
            JobListing("Unrelated Co", "Engineer", None, "https://x/2", "test"),
        ],
        dsn=seeded_db,
    )

    jobs = list_jobs(dsn=seeded_db, query="booking")

    assert len(jobs) == 1
    assert jobs[0].company_name == "Booking.com"


def test_reindex_all_jobs_pushes_every_row_into_the_default_index(
    seeded_db: str, meilisearch_env: tuple[str, str]
) -> None:
    """reindex_all_jobs() is the self-heal path web/app.py calls when the
    search index has gone missing (see its docstring) - it always targets
    the one real default index, not a test-isolated one, so this test
    cleans that index up itself afterward."""
    ingest_jobs(
        [JobListing("Booking.com", "Senior Backend Engineer", None, "https://x/1", "test")],
        dsn=seeded_db,
    )
    try:
        count = reindex_all_jobs(seeded_db)

        assert count == 1
        hits, total = meilisearch_client.search_jobs(query="backend")
        assert total == 1
        assert hits[0]["title"] == "Senior Backend Engineer"
    finally:
        meilisearch_client.delete_index()


def test_distinct_cities_returns_sorted_unique_locations(seeded_db: str) -> None:
    ingest_jobs(
        [
            JobListing("Booking.com", "A", "Amsterdam, Netherlands", "https://x/1", "test"),
            JobListing("Booking.com", "B", "Amsterdam, Netherlands", "https://x/2", "test"),
            JobListing("Booking.com", "C", "Rotterdam, Netherlands", "https://x/3", "test"),
            JobListing("Booking.com", "D", None, "https://x/4", "test"),
        ],
        dsn=seeded_db,
    )

    cities = distinct_cities(seeded_db)

    assert cities == ["Amsterdam, Netherlands", "Rotterdam, Netherlands"]


def test_list_jobs_multi_word_query_matches_words_out_of_order(seeded_db: str) -> None:
    """Regression: a single "%Platform engineer%" phrase substring missed
    "Client Platform Security Engineer" for a search of "Platform
    engineer" (an extra word between them breaks a phrase match) -
    confirmed live against the deployed site. Each word must match
    somewhere in title/company independently."""
    ingest_jobs(
        [
            JobListing("Acme", "Client Platform Security Engineer", None, "https://x/1", "test"),
            JobListing("Acme", "Data Analyst", None, "https://x/2", "test"),
        ],
        dsn=seeded_db,
    )

    jobs = list_jobs(dsn=seeded_db, query="Platform engineer")

    assert len(jobs) == 1
    assert jobs[0].title == "Client Platform Security Engineer"
