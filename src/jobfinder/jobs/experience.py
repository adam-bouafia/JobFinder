"""Heuristic experience-level classification for job titles.

Keyword-based, like open_applications.py - no LLM call, no job description
needed (titles are reliably available across every source; descriptions
aren't). "mid" is a fallback for titles with no explicit seniority signal,
not a confirmed classification - most untagged titles genuinely are
general/mid-level postings in practice, but treat it as a heuristic
default, not a guarantee.
"""

from __future__ import annotations

JUNIOR_KEYWORDS: tuple[str, ...] = (
    "junior",
    "graduate",
    "trainee",
    "intern",
    "internship",
    "entry level",
    "entry-level",
    "starter",
    "working student",
    "werkstudent",
    "stagiair",
    "stage",
)

SENIOR_KEYWORDS: tuple[str, ...] = (
    "senior",
    "staff",
    "lead",
    "principal",
    "head of",
    "director",
    "architect",
    "manager",
    "vp ",
    "chief",
)

EXPERIENCE_LEVELS: tuple[str, ...] = ("junior", "mid", "senior")


def classify_experience_level(title: str) -> str:
    lowered = title.lower()
    if any(keyword in lowered for keyword in SENIOR_KEYWORDS):
        return "senior"
    if any(keyword in lowered for keyword in JUNIOR_KEYWORDS):
        return "junior"
    return "mid"
