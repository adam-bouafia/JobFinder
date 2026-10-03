"""Tests for jobfinder.jobs.adzuna."""

from __future__ import annotations

import httpx
import pytest

from jobfinder.jobs.adzuna import AdzunaCredentialsError, search


def test_search_raises_a_clear_error_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)

    with pytest.raises(AdzunaCredentialsError, match="developer.adzuna.com"):
        search("software engineer")


def test_search_parses_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADZUNA_APP_ID", "fake-id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "fake-key")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[dict[str, object]]]:
            return {
                "results": [
                    {
                        "title": "Cloud Engineer",
                        "company": {"display_name": "Acme B.V."},
                        "location": {"display_name": "Amsterdam, Netherlands"},
                        "redirect_url": "https://adzuna.com/job/1",
                    }
                ]
            }

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())

    jobs = search("cloud engineer")

    assert len(jobs) == 1
    assert jobs[0].company_name == "Acme B.V."
    assert jobs[0].title == "Cloud Engineer"
    assert jobs[0].location == "Amsterdam, Netherlands"
    assert jobs[0].source == "adzuna"


def test_search_handles_missing_company_or_location(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADZUNA_APP_ID", "fake-id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "fake-key")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[dict[str, object]]]:
            return {"results": [{"title": "Mystery Role", "redirect_url": "https://x"}]}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())

    jobs = search("mystery")

    assert jobs[0].company_name == "Unknown"
    assert jobs[0].location is None
