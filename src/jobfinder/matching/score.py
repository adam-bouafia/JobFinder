"""Resume-derived job scoring: sponsor status + skill overlap + country fit.

Generalizes job-research's hardcoded, Adam-specific fit_score() into
resume-derived weights - whatever skills actually got extracted from the
currently loaded resume, not a fixed persona.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..db import cursor
from ..jobs.experience import classify_experience_level
from ..jobs.ingest import to_search_doc
from ..resume.parse import latest_resume_profile
from ..search import meilisearch_client

SPONSOR_BONUS = 5.0
SKILL_MATCH_WEIGHT = 1.0
COUNTRY_MATCH_BONUS = 1.0

_COUNTRY_HINTS: dict[str, tuple[str, ...]] = {
    "NL": ("netherlands", "nederland"),
}


def score_job(
    title: str,
    location: str | None,
    is_sponsor: bool,
    resume_skills: Sequence[str],
    country: str = "NL",
) -> float:
    """Score a job listing against a resume profile and sponsor status.

    Deliberately simple and inspectable, not an LLM call: sponsor status is
    the single biggest signal (this tool's whole point), then skill overlap
    with the resume's extracted skills, then a soft location/country bonus.
    Country matching is a substring check against a small hint list, not
    real geocoding - a reasonable heuristic, not a guarantee.
    """
    score = SPONSOR_BONUS if is_sponsor else 0.0

    lowered_title = title.lower()
    score += sum(SKILL_MATCH_WEIGHT for skill in resume_skills if skill.lower() in lowered_title)

    if location:
        hints = _COUNTRY_HINTS.get(country.upper(), ())
        if any(hint in location.lower() for hint in hints):
            score += COUNTRY_MATCH_BONUS

    return score


def rescore_jobs(dsn: str | None = None, country: str = "NL") -> int:
    """Recompute fit_score for every stored job against the latest resume
    profile (empty skill list if none has been parsed yet). Also backfills
    experience_level for any row ingested before that column existed -
    cheap and deterministic, so recomputing it unconditionally is fine.

    Returns the number of rows updated.
    """
    profile = latest_resume_profile(dsn)
    resume_skills = profile.skills if profile else []

    with cursor(dsn) as conn:
        rows = conn.execute("SELECT * FROM jobs").fetchall()
        docs = []
        for row in rows:
            score = score_job(
                title=row["title"],
                location=row["location"],
                is_sponsor=row["sponsor_kvk"] is not None,
                resume_skills=resume_skills,
                country=country,
            )
            experience_level = classify_experience_level(row["title"])
            conn.execute(
                "UPDATE jobs SET fit_score = %s, experience_level = %s WHERE id = %s",
                (score, experience_level, row["id"]),
            )
            docs.append(
                to_search_doc({**row, "fit_score": score, "experience_level": experience_level})
            )

    try:
        meilisearch_client.index_jobs(docs)
    except Exception as error:  # noqa: BLE001 - best-effort, see meilisearch_client docstring
        print(f"[search index] skipped: {error}")
    return len(rows)
