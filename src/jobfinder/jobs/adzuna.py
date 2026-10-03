"""Adzuna job search API client.

Needs free credentials: sign up at https://developer.adzuna.com/, create
an app, and set the ADZUNA_APP_ID / ADZUNA_APP_KEY environment variables
(never commit them - not something this module does on your behalf, since
registering an account is your call, not something to automate).
"""

from __future__ import annotations

import os

import httpx

from .models import JobListing

USER_AGENT = "JobFinder-JobIngest/0.1 (personal, non-commercial)"
BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


class AdzunaCredentialsError(RuntimeError):
    pass


def _credentials() -> tuple[str, str]:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise AdzunaCredentialsError(
            "Adzuna credentials not set. Sign up free at "
            "https://developer.adzuna.com/, then set the ADZUNA_APP_ID and "
            "ADZUNA_APP_KEY environment variables."
        )
    return app_id, app_key


def search(
    query: str, country: str = "nl", results_per_page: int = 50, page: int = 1
) -> list[JobListing]:
    """Search Adzuna for `query` (e.g. "software engineer").

    Raises:
        AdzunaCredentialsError: if ADZUNA_APP_ID/ADZUNA_APP_KEY aren't set.
    """
    app_id, app_key = _credentials()
    url = BASE_URL.format(country=country, page=page)
    params: dict[str, str | int] = {
        "app_id": app_id,
        "app_key": app_key,
        "what": query,
        "results_per_page": results_per_page,
        "content-type": "application/json",
    }
    response = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return [_to_listing(item) for item in response.json().get("results", [])]


def _to_listing(item: dict[str, object]) -> JobListing:
    company = item.get("company")
    location = item.get("location")
    company_name = company.get("display_name", "Unknown") if isinstance(company, dict) else None
    location_name = location.get("display_name") if isinstance(location, dict) else None
    return JobListing(
        company_name=company_name or "Unknown",
        title=str(item.get("title", "")),
        location=location_name,
        url=str(item.get("redirect_url", "")),
        source="adzuna",
    )
