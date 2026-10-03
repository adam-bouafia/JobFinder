"""Ashby's public job-board API - no authentication needed."""

from __future__ import annotations

import httpx

from ..models import JobListing
from ._html import plain_text

USER_AGENT = "JobFinder-JobIngest/0.1 (personal, non-commercial)"


def fetch(slug: str) -> list[JobListing]:
    """Fetch open roles for a company's Ashby board.

    `descriptionHtml` is best-effort - not verified against a live board
    the way the title/location/url fields were, so it can be missing
    without that meaning anything is wrong.
    """
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    response = httpx.get(
        url,
        headers={"User-Agent": USER_AGENT},
        params={"includeCompensation": "false"},
        timeout=30,
    )
    if response.status_code != 200:
        return []
    jobs = response.json().get("jobs", [])
    return [
        JobListing(
            company_name=slug,
            title=job.get("title", ""),
            location=job.get("locationName"),
            url=job.get("jobUrl") or f"https://jobs.ashbyhq.com/{slug}/{job.get('id')}",
            source="ashby",
            description=plain_text(job.get("descriptionHtml")),
        )
        for job in jobs
    ]
