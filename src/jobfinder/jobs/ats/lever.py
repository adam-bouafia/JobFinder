"""Lever's public job-postings JSON API - no authentication needed."""

from __future__ import annotations

import httpx

from ..models import JobListing

USER_AGENT = "JobFinder-JobIngest/0.1 (personal, non-commercial)"


def fetch(slug: str) -> list[JobListing]:
    """Fetch open roles for a company's Lever board."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    if response.status_code != 200:
        return []
    return [
        JobListing(
            company_name=slug,
            title=job["text"],
            location=(job.get("categories") or {}).get("location"),
            url=job["hostedUrl"],
            source="lever",
        )
        for job in response.json()
    ]
