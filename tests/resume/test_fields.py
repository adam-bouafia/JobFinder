"""Tests for jobfinder.resume.fields."""

from __future__ import annotations

from datetime import date

import pytest

from jobfinder.resume.fields import extract_education, extract_skills, extract_years_experience

RESUME_TEXT = """
Jane Doe
Senior Backend Engineer

Experience
2019 - 2023   Backend Engineer, Acme Corp
              Built services in Python and Go, deployed on AWS with
              Kubernetes and Terraform. Used PostgreSQL and Redis.
2023 - Present   Staff Engineer, Example Inc

Education
MSc Computer Science, University of Somewhere
BSc Software Engineering, Another University
"""


def test_extract_skills_finds_vocabulary_terms_present_in_text() -> None:
    skills = extract_skills(RESUME_TEXT)
    assert "python" in skills
    assert "go" in skills
    assert "aws" in skills
    assert "kubernetes" in skills
    assert "terraform" in skills
    assert "postgresql" in skills
    assert "redis" in skills


def test_extract_skills_ignores_terms_not_present() -> None:
    skills = extract_skills(RESUME_TEXT)
    assert "java" not in skills
    assert "rust" not in skills


@pytest.mark.parametrize(
    ("text", "skill"),
    [
        ("Experience with C++ and embedded systems.", "c++"),
        ("Built APIs with .NET and C#.", "c#"),
        ("Strong project management background.", "project management"),
    ],
)
def test_extract_skills_handles_symbol_and_multiword_skills(text: str, skill: str) -> None:
    assert skill in extract_skills(text)


def test_extract_skills_does_not_match_substring_of_a_longer_token() -> None:
    # "go" must not match inside "going" or "algorithm"
    assert extract_skills("We are going to review the algorithm.") == []


def test_extract_years_experience_sums_date_ranges() -> None:
    years = extract_years_experience(RESUME_TEXT, today=date(2026, 1, 1))
    # 2019-2023 (4) + 2023-2026 "Present" (3) = 7
    assert years == 7.0


def test_extract_years_experience_returns_none_without_a_date_range() -> None:
    assert extract_years_experience("No dates here at all.") is None


@pytest.mark.parametrize(
    "text",
    ["2020-2024", "2020 - 2024", "2020 to 2024", "2020–2024", "2020—2024"],
)
def test_extract_years_experience_handles_dash_variants(text: str) -> None:
    assert extract_years_experience(text, today=date(2026, 1, 1)) == 4.0


def test_extract_education_returns_degree_lines_in_order() -> None:
    education = extract_education(RESUME_TEXT)
    assert education == [
        "MSc Computer Science, University of Somewhere",
        "BSc Software Engineering, Another University",
    ]


def test_extract_education_returns_empty_list_when_no_degree_mentioned() -> None:
    assert extract_education("No education section here.") == []
