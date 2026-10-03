"""Tests for jobfinder.jobs.jsearch."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from jobfinder.jobs import jsearch


class FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


def test_search_raises_a_clear_error_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAPIDAPI_KEY", raising=False)

    with pytest.raises(jsearch.JSearchCredentialsError, match="rapidapi.com"):
        jsearch.search("platform engineer")


def test_search_keeps_only_employer_domain_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "fake-key")
    payload = {
        "status": "OK",
        "data": {
            "jobs": [
                {
                    "job_title": "Platform Engineer",
                    "employer_name": "Catawiki",
                    "job_apply_link": "https://catawiki.careers/vacancies/platform-engineer",
                    "job_city": "Amsterdam",
                    "job_country": "NL",
                    "job_description": "Build our platform.",
                },
                {
                    "job_title": "Platform Engineer",
                    "employer_name": "Wypoon Technologies",
                    "job_apply_link": "https://nl.linkedin.com/jobs/view/platform-engineer",
                    "job_city": "Amsterdam",
                    "job_country": "NL",
                },
            ]
        },
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(200, payload))

    listings = jsearch.search("platform engineer")

    assert len(listings) == 1
    assert listings[0].company_name == "Catawiki"
    assert listings[0].url == "https://catawiki.careers/vacancies/platform-engineer"
    assert listings[0].source == "jsearch"
    assert listings[0].description == "Build our platform."
    assert listings[0].location == "Amsterdam, NL"


def test_search_rejects_a_job_board_not_on_any_blocklist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: a hand-maintained publisher-name blocklist was tried
    first and missed ictergezocht.nl (a real Dutch IT job board) for a
    "CGI Nederland" posting - the domain-matching check must reject it
    even though it's never been seen/listed before."""
    monkeypatch.setenv("RAPIDAPI_KEY", "fake-key")
    payload = {
        "status": "OK",
        "data": {
            "jobs": [
                {
                    "job_title": "Data & AI Platform Engineer",
                    "employer_name": "CGI Nederland",
                    "job_apply_link": "https://www.ictergezocht.nl/ict-vacature/424009",
                    "job_city": "Amsterdam",
                    "job_country": "NL",
                }
            ]
        },
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(200, payload))

    listings = jsearch.search("platform engineer")

    assert listings == []


def test_search_handles_missing_city_or_country(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "fake-key")
    payload = {
        "status": "OK",
        "data": {
            "jobs": [
                {
                    "job_title": "Platform Engineer",
                    "employer_name": "Catawiki",
                    "job_apply_link": "https://catawiki.careers/vacancies/platform-engineer",
                }
            ]
        },
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(200, payload))

    listings = jsearch.search("platform engineer")

    assert listings[0].location is None


@pytest.mark.parametrize(
    ("employer", "url", "expected"),
    [
        ("Catawiki", "https://catawiki.careers/vacancies/platform-engineer", True),
        ("Booking.com", "https://jobs.booking.com/booking/jobs/30161", True),
        (
            "Werken bij de Belastingdienst",
            "https://werken.belastingdienst.nl/vacatures/e12381",
            True,
        ),
        ("Linden-IT", "https://linden-it.com/vacatures/medior-senior-platform-engineer", True),
        ("Wypoon Technologies", "https://nl.linkedin.com/jobs/view/ai-platform-engineer", False),
        ("Budget Thuis", "https://nl.indeed.com/viewjob?jk=3ddf40d102404608", False),
        ("Hot ITem Groep", "https://www.werkzoeken.nl/vacature/16155947", False),
        ("CGI Nederland", "https://www.ictergezocht.nl/ict-vacature/424009", False),
    ],
)
def test_looks_like_employer_domain_matches_live_verified_cases(
    employer: str, url: str, expected: bool
) -> None:
    """Pins down the exact real-world cases checked live against JSearch
    (see jsearch.py's module docstring) - genuine employer domains score
    100, every third-party board tried scored <=47."""
    assert jsearch._looks_like_employer_domain(employer, url) is expected
