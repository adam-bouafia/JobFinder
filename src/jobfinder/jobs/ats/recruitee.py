"""Recruitee's public offers API - no authentication needed."""

from __future__ import annotations

import httpx

from ..models import JobListing
from ._html import plain_text

USER_AGENT = "JobFinder-JobIngest/0.1 (personal, non-commercial)"


def fetch(slug: str) -> list[JobListing]:
    """Fetch open roles for a company's Recruitee board.

    `description` is best-effort - not verified against a live board the
    way the title/location/url fields were, so it can be missing without
    that meaning anything is wrong.
    """
    url = f"https://{slug}.recruitee.com/api/offers/"
    response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    if response.status_code != 200:
        return []
    offers = response.json().get("offers", [])
    return [
        JobListing(
            company_name=slug,
            title=offer.get("title", ""),
            location=offer.get("location"),
            url=offer.get("careers_url") or offer.get("url", ""),
            source="recruitee",
            description=plain_text(offer.get("description")),
        )
        for offer in offers
    ]
