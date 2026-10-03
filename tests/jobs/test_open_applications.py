"""Tests for jobfinder.jobs.open_applications."""

from __future__ import annotations

import pytest

from jobfinder.jobs.open_applications import is_open_application


@pytest.mark.parametrize(
    "title",
    [
        "General Application",
        "Open Application - Engineering",
        "Future Opportunities at Acme",
        "Talent Pool: Software Engineers",
        "Open sollicitatie",
    ],
)
def test_is_open_application_recognises_known_phrasings(title: str) -> None:
    assert is_open_application(title) is True


@pytest.mark.parametrize(
    "title",
    ["Senior Backend Engineer", "Site Reliability Engineer", "Data Analyst"],
)
def test_is_open_application_rejects_ordinary_titles(title: str) -> None:
    assert is_open_application(title) is False
