"""Workable's public widget API - no authentication needed."""

from __future__ import annotations

import httpx

from ..models import JobListing

USER_AGENT = "JobFinder-JobIngest/0.1 (personal, non-commercial)"


def fetch(slug: str) -> list[JobListing]:
    """Fetch open roles for a company's Workable board."""
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
    response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    if response.status_code != 200:
        return []
    jobs = response.json().get("jobs", [])
    return [
        JobListing(
            company_name=slug,
            title=job.get("title", ""),
            location=", ".join(filter(None, [job.get("city"), job.get("country")])) or None,
            url=job.get("url") or f"https://apply.workable.com/{slug}/j/{job.get('shortcode')}",
            source="workable",
        )
        for job in jobs
    ]
