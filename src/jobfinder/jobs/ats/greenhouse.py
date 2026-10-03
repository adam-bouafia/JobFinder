"""Greenhouse's public job-board JSON API - no authentication needed."""

from __future__ import annotations

import httpx

from ..models import JobListing

USER_AGENT = "JobFinder-JobIngest/0.1 (personal, non-commercial)"


def fetch(slug: str) -> list[JobListing]:
    """Fetch open roles for a company's Greenhouse board (e.g. "stripe")."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    if response.status_code != 200:
        return []
    jobs = response.json().get("jobs", [])
    return [
        JobListing(
            company_name=slug,
            title=job["title"],
            location=(job.get("location") or {}).get("name"),
            url=job["absolute_url"],
            source="greenhouse",
        )
        for job in jobs
    ]
