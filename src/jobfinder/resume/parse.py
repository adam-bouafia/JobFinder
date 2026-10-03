"""Orchestrates PDF -> text -> structured fields -> a stored resume profile."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..db import cursor
from ..paths import DB_PATH
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


def parse_resume(path: Path, db_path: Path = DB_PATH) -> ResumeProfile:
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

    with cursor(db_path) as conn:
        conn.execute(
            """
            INSERT INTO resume_profile
                (source_path, raw_text, skills, years_experience, education, parsed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                profile.source_path,
                profile.raw_text,
                json.dumps(profile.skills),
                profile.years_experience,
                json.dumps(profile.education),
                profile.parsed_at,
            ),
        )

    return profile


def latest_resume_profile(db_path: Path = DB_PATH) -> ResumeProfile | None:
    """Return the most recently parsed resume profile, if any."""
    with cursor(db_path) as conn:
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
        skills=json.loads(row["skills"]),
        years_experience=row["years_experience"],
        education=json.loads(row["education"]),
        parsed_at=row["parsed_at"],
    )
