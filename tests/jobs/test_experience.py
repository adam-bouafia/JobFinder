"""Tests for jobfinder.jobs.experience."""

from __future__ import annotations

import pytest

from jobfinder.jobs.experience import classify_experience_level


@pytest.mark.parametrize(
    "title",
    [
        "Junior Software Engineer",
        "Graduate Program - Engineering",
        "Software Engineering Intern",
        "Working Student Data Science",
        "Trainee Consultant",
    ],
)
def test_classify_experience_level_recognises_junior_titles(title: str) -> None:
    assert classify_experience_level(title) == "junior"


@pytest.mark.parametrize(
    "title",
    [
        "Senior Software Engineer",
        "Staff Engineer",
        "Engineering Lead",
        "Principal Architect",
        "Head of Engineering",
        "Engineering Manager",
    ],
)
def test_classify_experience_level_recognises_senior_titles(title: str) -> None:
    assert classify_experience_level(title) == "senior"


@pytest.mark.parametrize("title", ["Software Engineer", "Backend Developer", "Data Analyst"])
def test_classify_experience_level_defaults_to_mid(title: str) -> None:
    assert classify_experience_level(title) == "mid"


def test_classify_experience_level_prefers_senior_over_junior_when_both_present() -> None:
    # Contrived, but the classifier should still resolve unambiguously.
    assert classify_experience_level("Senior Trainee Program Lead") == "senior"
