"""Orchestrates PDF -> text -> structured fields -> a stored resume profile."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..db import cursor
from .extract import extract_text
from .fields import extract_education, extract_skills, extract_years_experience


@dataclass(frozen=True)
class ResumeProfile:
    source_path: str
    raw_text: str
    skills: list[str]
    years_experience: float | None
    education: list[str]
    parsed_at: str


def parse_resume(path: Path, dsn: str | None = None) -> ResumeProfile:
    """Extract text from `path`, derive a structured profile, and store it."""
    pages = extract_text(path)
    raw_text = "\n".join(pages)

    profile = ResumeProfile(
        source_path=str(path),
        raw_text=raw_text,
        skills=extract_skills(raw_text),
        years_experience=extract_years_experience(raw_text),
        education=extract_education(raw_text),
        parsed_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )

    with cursor(dsn) as conn:
        conn.execute(
            """
            INSERT INTO resume_profile
                (source_path, raw_text, skills, years_experience, education, parsed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                profile.source_path,
                profile.raw_text,
                profile.skills,
                profile.years_experience,
                profile.education,
                profile.parsed_at,
            ),
        )

    return profile


def latest_resume_profile(dsn: str | None = None) -> ResumeProfile | None:
    """Return the most recently parsed resume profile, if any."""
    with cursor(dsn) as conn:
        # id DESC as a tiebreaker: parsed_at has only second precision, so
        # two parses within the same second would otherwise sort
        # ambiguously.
        row = conn.execute(
            "SELECT * FROM resume_profile ORDER BY parsed_at DESC, id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return ResumeProfile(
        source_path=row["source_path"],
        raw_text=row["raw_text"],
        skills=row["skills"],
        years_experience=row["years_experience"],
        education=row["education"],
        parsed_at=row["parsed_at"].isoformat(timespec="seconds"),
    )
