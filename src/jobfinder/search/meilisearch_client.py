"""Thin Meilisearch REST client for the jobs search index.

Plain httpx, not the official `meilisearch` SDK - same pattern as every
other external integration in this codebase (Adzuna used to, the ATS
fetchers still do), one fewer dependency for a handful of simple calls.

Postgres (db.py) stays the system of record. This index is a derived,
rebuildable projection of the jobs table, built specifically for fast,
typo-tolerant, ranked free-text search - something plain SQL ILIKE can't
do well. If Meilisearch is ever unreachable, callers are expected to
degrade gracefully (see jobs/ingest.py, web/app.py) rather than fail
outright: the CLI works fully against Postgres with no index at all.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

DEFAULT_INDEX = "jobs"
# Deliberately not "description": verified live against 716 real postings
# that including it turns a search like "platform" into a near-useless
# 678/716 match (long descriptions mention almost any common word
# somewhere), vs. 51 precise title/company matches without it - same
# scope the old SQL ILIKE search had, just with typo tolerance added.
SEARCHABLE_ATTRIBUTES = ["title", "company_name"]
FILTERABLE_ATTRIBUTES = ["sponsor_kvk", "is_open_application", "experience_level", "location"]


class MeilisearchConfigError(RuntimeError):
    pass


def _config() -> tuple[str, str]:
    url = os.environ.get("MEILISEARCH_URL")
    key = os.environ.get("MEILISEARCH_KEY")
    if not url or not key:
        raise MeilisearchConfigError(
            "MEILISEARCH_URL / MEILISEARCH_KEY are not set - see .env / deploy/README.md."
        )
    return url.rstrip("/"), key


def _client() -> httpx.Client:
    url, key = _config()
    return httpx.Client(base_url=url, headers={"Authorization": f"Bearer {key}"}, timeout=30)


def _wait_for_task(client: httpx.Client, task_uid: int, timeout: float = 30.0) -> None:
    """Meilisearch writes are async - every mutating call just returns an
    enqueued task immediately. Confirmed live: searching (or even just
    creating an index) right after writing to it can race the task and
    404/return stale results. Block until it's actually done, so callers
    can trust "this function returned, the write has taken effect."
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/tasks/{task_uid}")
        response.raise_for_status()
        status = response.json()["status"]
        if status in ("succeeded", "failed", "canceled"):
            return
        time.sleep(0.05)
    raise TimeoutError(f"Meilisearch task {task_uid} did not finish within {timeout}s")


def ensure_index(index: str = DEFAULT_INDEX) -> None:
    """Idempotent: create the index with the right settings if it doesn't
    exist yet, and turn on the `containsFilter` experimental feature the
    city filter depends on (confirmed required - CONTAINS/STARTS WITH are
    gated behind it as of Meilisearch 1.11, see
    github.com/orgs/meilisearch/discussions/763)."""
    with _client() as client:
        client.patch("/experimental-features", json={"containsFilter": True})

        # Creating an already-existing index is also a 202 (verified live,
        # not a synchronous 400) - the task then just fails asynchronously
        # with "index_already_exists", which _wait_for_task tolerates as a
        # terminal status without raising. Idempotent either way.
        create = client.post("/indexes", json={"uid": index, "primaryKey": "id"})
        create.raise_for_status()
        _wait_for_task(client, create.json()["taskUid"])

        settings = client.patch(
            f"/indexes/{index}/settings",
            json={
                "searchableAttributes": SEARCHABLE_ATTRIBUTES,
                "filterableAttributes": FILTERABLE_ATTRIBUTES,
            },
        )
        settings.raise_for_status()
        _wait_for_task(client, settings.json()["taskUid"])


_ensured: set[str] = set()


def index_jobs(jobs: list[dict[str, Any]], index: str = DEFAULT_INDEX) -> None:
    """Upsert job documents (by `id`) into the index.

    Ensures the index/settings exist first, but only once per process
    (ensure_index() makes 2-3 HTTP round-trips - fine as a one-off, not
    worth paying on every single ingest/rescore call).
    """
    if not jobs:
        return
    if index not in _ensured:
        ensure_index(index)
        _ensured.add(index)
    with _client() as client:
        response = client.put(f"/indexes/{index}/documents", json=jobs)
        response.raise_for_status()
        _wait_for_task(client, response.json()["taskUid"])


def delete_index(index: str = DEFAULT_INDEX) -> None:
    """Drop the index entirely - used by tests for cleanup."""
    with _client() as client:
        client.delete(f"/indexes/{index}")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def search_jobs(
    *,
    query: str | None = None,
    city: str | None = None,
    sponsors_only: bool = False,
    open_applications_only: bool = False,
    experience_level: str | None = None,
    limit: int = 100,
    index: str = DEFAULT_INDEX,
) -> tuple[list[dict[str, Any]], int]:
    """Ranked, typo-tolerant search + filtering. Returns (hits, estimated_total_hits)."""
    filters: list[str] = []
    if city:
        filters.append(f'location CONTAINS "{_escape(city)}"')
    if sponsors_only:
        filters.append("sponsor_kvk IS NOT NULL")
    if open_applications_only:
        filters.append("is_open_application = true")
    if experience_level:
        filters.append(f'experience_level = "{_escape(experience_level)}"')

    payload: dict[str, Any] = {"q": query or "", "limit": limit}
    if filters:
        payload["filter"] = " AND ".join(filters)

    with _client() as client:
        response = client.post(f"/indexes/{index}/search", json=payload)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
    return data["hits"], data["estimatedTotalHits"]
