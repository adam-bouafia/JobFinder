"""Tests for jobfinder.search.meilisearch_client, against a real
Meilisearch instance (see tests/conftest.py) - no mocking, same
principle as the Postgres-backed tests elsewhere in this suite."""

from __future__ import annotations

from jobfinder.search import meilisearch_client

SAMPLE_JOB: dict[str, object] = {
    "id": 1,
    "company_name": "Booking.com",
    "title": "Senior Backend Engineer",
    "location": "Amsterdam, Netherlands",
    "url": "https://example.com/job/1",
    "source": "greenhouse",
    "is_open_application": False,
    "sponsor_kvk": "31047344",
    "fit_score": 6.0,
    "experience_level": "senior",
    "description": "Build and maintain backend services.",
    "fetched_at": "2026-10-01T00:00:00",
}


def test_index_and_search_roundtrip(search_index: str) -> None:
    meilisearch_client.index_jobs([SAMPLE_JOB], index=search_index)

    hits, total = meilisearch_client.search_jobs(query="backend", index=search_index)

    assert total == 1
    assert hits[0]["title"] == "Senior Backend Engineer"


def test_search_is_typo_tolerant_on_title(search_index: str) -> None:
    meilisearch_client.index_jobs([SAMPLE_JOB], index=search_index)

    hits, total = meilisearch_client.search_jobs(query="bakend", index=search_index)

    assert total == 1
    assert hits[0]["id"] == 1


def test_search_does_not_match_description_text(search_index: str) -> None:
    """Deliberately narrow: searching the free-text box should only match
    title/company, not the (long, generic) description - verified live
    that including description turned a search like "platform" into a
    near-useless 678/716 match against real job postings."""
    meilisearch_client.index_jobs([SAMPLE_JOB], index=search_index)

    hits, total = meilisearch_client.search_jobs(query="maintain", index=search_index)

    assert total == 0
    assert hits == []


def test_search_filters_by_sponsors_only(search_index: str) -> None:
    unsponsored = {**SAMPLE_JOB, "id": 2, "url": "https://example.com/job/2", "sponsor_kvk": None}
    meilisearch_client.index_jobs([SAMPLE_JOB, unsponsored], index=search_index)

    hits, total = meilisearch_client.search_jobs(sponsors_only=True, index=search_index)

    assert total == 1
    assert hits[0]["id"] == 1


def test_search_filters_by_open_applications_only(search_index: str) -> None:
    open_app = {
        **SAMPLE_JOB,
        "id": 2,
        "url": "https://example.com/job/2",
        "is_open_application": True,
    }
    meilisearch_client.index_jobs([SAMPLE_JOB, open_app], index=search_index)

    hits, total = meilisearch_client.search_jobs(open_applications_only=True, index=search_index)

    assert total == 1
    assert hits[0]["id"] == 2


def test_search_filters_by_experience_level(search_index: str) -> None:
    junior = {
        **SAMPLE_JOB,
        "id": 2,
        "url": "https://example.com/job/2",
        "experience_level": "junior",
    }
    meilisearch_client.index_jobs([SAMPLE_JOB, junior], index=search_index)

    hits, total = meilisearch_client.search_jobs(experience_level="junior", index=search_index)

    assert total == 1
    assert hits[0]["id"] == 2


def test_search_filters_by_city_substring(search_index: str) -> None:
    berlin = {
        **SAMPLE_JOB,
        "id": 2,
        "url": "https://example.com/job/2",
        "location": "Berlin, Germany",
    }
    meilisearch_client.index_jobs([SAMPLE_JOB, berlin], index=search_index)

    hits, total = meilisearch_client.search_jobs(city="Amsterdam", index=search_index)

    assert total == 1
    assert hits[0]["id"] == 1


def test_index_jobs_upserts_by_id(search_index: str) -> None:
    meilisearch_client.index_jobs([SAMPLE_JOB], index=search_index)
    updated = {**SAMPLE_JOB, "fit_score": 9.0}

    meilisearch_client.index_jobs([updated], index=search_index)

    hits, total = meilisearch_client.search_jobs(query="backend", index=search_index)
    assert total == 1
    assert hits[0]["fit_score"] == 9.0


def test_index_jobs_with_empty_list_does_not_raise(search_index: str) -> None:
    # Deliberately doesn't create the index first (that's the point -
    # an empty batch should be a true no-op, not even an index-creation
    # call) - just asserting this doesn't raise.
    meilisearch_client.index_jobs([], index=search_index)
