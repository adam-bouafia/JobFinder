"""Heuristic extraction of structured fields from resume text.

No LLM calls, no persona bias: skills are "whatever vocabulary terms
appear in this specific resume," not a fixed profile. Extend
SKILL_VOCABULARY over time rather than hardcoding one person's stack
(job-research's profile.py took the opposite, Adam-specific approach -
deliberately not repeating that here).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date

SKILL_VOCABULARY: tuple[str, ...] = (
    # Languages
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "c#",
    "go",
    "golang",
    "rust",
    "ruby",
    "php",
    "swift",
    "kotlin",
    "scala",
    "sql",
    "bash",
    "dart",
    # Web / frontend
    "react",
    "vue",
    "angular",
    "html",
    "css",
    "next.js",
    "node.js",
    # Backend frameworks
    "django",
    "flask",
    "fastapi",
    "spring",
    "express",
    "rails",
    ".net",
    # Cloud / infra
    "aws",
    "azure",
    "gcp",
    "kubernetes",
    "docker",
    "terraform",
    "ansible",
    "jenkins",
    "github actions",
    "gitlab ci",
    "ci/cd",
    "bicep",
    # Data / ML
    "pandas",
    "numpy",
    "pytorch",
    "tensorflow",
    "scikit-learn",
    "spark",
    "hadoop",
    "airflow",
    "machine learning",
    "deep learning",
    # Databases
    "postgresql",
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "elasticsearch",
    "sqlite",
    # Observability
    "grafana",
    "prometheus",
    "datadog",
    # General professional
    "agile",
    "scrum",
    "project management",
    "leadership",
)

_DEGREE_KEYWORDS = re.compile(
    r"(?<!\w)(ph\.?d|doctorate|m\.?sc|master'?s?|m\.?a\.?|b\.?sc|"
    r"bachelor'?s?|b\.?a\.?|associate degree)(?!\w)",
    re.IGNORECASE,
)

_YEAR = r"(?:19|20)\d{2}"
_PRESENT_WORDS = {"present", "current", "now", "today"}
_DATE_RANGE = re.compile(
    rf"(?P<start>{_YEAR})\s*(?:[-–—]|to)\s*(?P<end>{_YEAR}|present|current|now|today)",
    re.IGNORECASE,
)


def _skill_pattern(skill: str) -> re.Pattern[str]:
    # Not \b: that breaks on symbol-containing skills like "C++" or ".NET"
    # (\b needs a word/non-word transition, but "+" and "+" are both
    # non-word, so \b never matches between them). This isolates the skill
    # by requiring non-word characters (or a string boundary) on each side
    # instead, which works for plain words and symbol-containing ones alike.
    return re.compile(rf"(?<!\w){re.escape(skill)}(?!\w)", re.IGNORECASE)


def extract_skills(text: str, vocabulary: Sequence[str] = SKILL_VOCABULARY) -> list[str]:
    """Return vocabulary terms that appear in `text`, in vocabulary order."""
    return [skill for skill in vocabulary if _skill_pattern(skill).search(text)]


def extract_years_experience(text: str, today: date | None = None) -> float | None:
    """Sum the spans of date ranges found in `text` (e.g. "2019 - 2023").

    Heuristic, not exact: overlapping ranges (e.g. two concurrent roles)
    are double-counted rather than merged, and a range with no recognisable
    year pair just doesn't count. Returns None if no date range is found
    at all.
    """
    today = today or date.today()
    spans: list[int] = []
    for match in _DATE_RANGE.finditer(text):
        start_year = int(match.group("start"))
        end_raw = match.group("end").lower()
        end_year = today.year if end_raw in _PRESENT_WORDS else int(end_raw)
        if end_year >= start_year:
            spans.append(end_year - start_year)
    if not spans:
        return None
    return float(sum(spans))


def extract_education(text: str) -> list[str]:
    """Return resume lines mentioning a degree, in document order, deduped."""
    seen: set[str] = set()
    results: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line in seen:
            continue
        if _DEGREE_KEYWORDS.search(line):
            results.append(line)
            seen.add(line)
    return results
