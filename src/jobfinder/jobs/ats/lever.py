"""Lever's public job-postings JSON API - no authentication needed."""

from __future__ import annotations

import httpx

from ..models import JobListing
from ._html import plain_text

USER_AGENT = "JobFinder-JobIngest/0.1 (personal, non-commercial)"


def fetch(slug: str) -> list[JobListing]:
    """Fetch open roles for a company's Lever board.

    `description` (the posting's HTML intro, ahead of its "lists"
    sections like Requirements) is best-effort - not verified against a
    live board the way the title/location/url fields were, so it can be
    missing without that meaning anything is wrong.
    """
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
            description=plain_text(job.get("description")),
        )
        for job in response.json()
    ]
