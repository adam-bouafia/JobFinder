"""JSearch (RapidAPI) job search client - aggregates Google for Jobs,
which itself pulls from LinkedIn, Indeed, Glassdoor, company career
pages, and more.

Checked JSearch's real terms (openwebninja.com/terms): commercial use of
API Data is explicitly licensed ("non-exclusive, non-transferable
license to use, reproduce, and commercially exploit API Data in your own
products"), no "Jobs by X" attribution badge required the way Adzuna's
terms did - see docs/architecture.md's risk table for the full Adzuna
comparison.

Live-verified (2026-10-03, real NL "platform engineer" search) that
`job_apply_is_direct` / `apply_options[].is_direct` does NOT mean "this
is the employer's own domain" - all 10 real results had is_direct=false,
including genuine employer career pages (catawiki.careers,
werken.belastingdienst.nl). It appears to track Google's own one-click-
apply UI integration, not domain ownership - not a signal this project
can use.

Directness is enforced here instead by checking whether the apply link's
own domain actually relates to the employer's name (rapidfuzz
partial_ratio, same technique sponsors/match.py uses for a different
problem) - verified live across 11 real results that this cleanly
separates genuine employer domains (score 100: catawiki.careers for
"Catawiki", jobs.booking.com for "Booking.com") from third-party boards
(score <=47: linkedin.com, indeed.com, werkzoeken.nl, jobleads.com, and
one - ictergezocht.nl for "CGI Nederland" - that a hand-maintained
publisher-name blocklist tried first and missed, which is exactly why
this self-verifying approach replaced it rather than supplementing it).

Free tier is 200 requests/month - deliberately CLI-only (`jf search-
jobs`), not wired into the web UI's automatic search, which would burn
through that in minutes.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import httpx
from rapidfuzz import fuzz

from .models import JobListing

USER_AGENT = "JobFinder-JobIngest/0.1 (personal, non-commercial)"
BASE_URL = "https://jsearch.p.rapidapi.com/search-v2"
API_HOST = "jsearch.p.rapidapi.com"
DIRECT_DOMAIN_THRESHOLD = 70.0


class JSearchCredentialsError(RuntimeError):
    pass


def _credentials() -> str:
    key = os.environ.get("RAPIDAPI_KEY")
    if not key:
        raise JSearchCredentialsError(
            "RAPIDAPI_KEY is not set. Sign up free at rapidapi.com, subscribe "
            "to JSearch specifically (not just having an account), then set "
            "RAPIDAPI_KEY."
        )
    return key


def _domain_label(url: str) -> str:
    """The most specific label of the URL's registrable domain, e.g.
    "catawiki" from "catawiki.careers", "belastingdienst" from
    "werken.belastingdienst.nl". Doesn't handle multi-part TLDs like
    .co.uk - an acceptable gap for a NL-focused tool."""
    host = urlparse(url).netloc.lower().split(":")[0]
    parts = host.split(".")
    return parts[-2] if len(parts) >= 2 else (parts[0] if parts else "")


def _looks_like_employer_domain(employer_name: str, url: str) -> bool:
    """Is `url` plausibly the employer's own site, not a third-party job
    board? See module docstring for the live verification behind this."""
    normalized_employer = re.sub(r"[^a-z0-9]", "", employer_name.lower())
    label = re.sub(r"[^a-z0-9]", "", _domain_label(url))
    if not normalized_employer or not label:
        return False
    return fuzz.partial_ratio(normalized_employer, label) >= DIRECT_DOMAIN_THRESHOLD


def search(query: str, country: str = "nl", num_pages: int = 1) -> list[JobListing]:
    """Search JSearch for `query`, keeping only results whose apply link
    looks like the employer's own domain - consistent with this
    project's direct-link-only design (see module docstring).

    Raises:
        JSearchCredentialsError: if RAPIDAPI_KEY isn't set.
    """
    key = _credentials()
    params: dict[str, str | int] = {
        "query": query,
        "country": country,
        "num_pages": num_pages,
        "date_posted": "all",
    }
    response = httpx.get(
        BASE_URL,
        params=params,
        headers={"User-Agent": USER_AGENT, "x-rapidapi-host": API_HOST, "x-rapidapi-key": key},
        timeout=30,
    )
    response.raise_for_status()
    jobs = response.json().get("data", {}).get("jobs", [])
    listings = [_to_listing(job) for job in jobs]
    return [
        listing
        for listing, job in zip(listings, jobs, strict=True)
        if _looks_like_employer_domain(str(job.get("employer_name", "")), listing.url)
    ]


def _to_listing(item: dict[str, object]) -> JobListing:
    city = item.get("job_city")
    country_code = item.get("job_country")
    location = ", ".join(str(part) for part in (city, country_code) if part) or None
    description = item.get("job_description")
    return JobListing(
        company_name=str(item.get("employer_name") or "Unknown"),
        title=str(item.get("job_title", "")),
        location=location,
        url=str(item.get("job_apply_link", "")),
        source="jsearch",
        description=description if isinstance(description, str) else None,
    )
