"""Tests for jobfinder.matching.score."""

from __future__ import annotations

from pathlib import Path

from jobfinder import db
from jobfinder.jobs.ingest import ingest_jobs, list_jobs
from jobfinder.jobs.models import JobListing
from jobfinder.matching.score import rescore_jobs, score_job
from jobfinder.sponsors.normalize import normalize


def test_score_job_rewards_sponsor_status() -> None:
    sponsor_score = score_job("Engineer", None, is_sponsor=True, resume_skills=[])
    non_sponsor_score = score_job("Engineer", None, is_sponsor=False, resume_skills=[])
    assert sponsor_score > non_sponsor_score


def test_score_job_rewards_skill_overlap() -> None:
    matching = score_job(
        "Senior Python Engineer", None, is_sponsor=False, resume_skills=["python", "kubernetes"]
    )
    non_matching = score_job(
        "Senior Java Engineer", None, is_sponsor=False, resume_skills=["python", "kubernetes"]
    )
    assert matching > non_matching


def test_score_job_rewards_country_match() -> None:
    nl = score_job("Engineer", "Amsterdam, Netherlands", is_sponsor=False, resume_skills=[])
    elsewhere = score_job("Engineer", "Berlin, Germany", is_sponsor=False, resume_skills=[])
    assert nl > elsewhere


def test_rescore_jobs_updates_fit_score_from_latest_resume(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with db.cursor(db_path) as conn:
        conn.execute(
            "INSERT INTO sponsors (kvk, name, name_normalized, fetched_at) VALUES (?, ?, ?, ?)",
            ("31047344", "Booking.com B.V.", normalize("Booking.com B.V."), "2026-10-01"),
        )
        conn.execute(
            "INSERT INTO resume_profile "
            "(source_path, raw_text, skills, years_experience, education, parsed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("resume.pdf", "...", '["python", "kubernetes"]', 5.0, "[]", "2026-10-01"),
        )

    ingest_jobs(
        [JobListing("Booking.com", "Senior Python Engineer", "Amsterdam", "https://x/1", "test")],
        db_path=db_path,
    )

    updated = rescore_jobs(db_path=db_path)

    assert updated == 1
    jobs = list_jobs(db_path=db_path)
    # sponsor (5) + python skill match (1) -- "kubernetes" isn't in the title
    assert jobs[0].fit_score == 6.0


def test_rescore_jobs_with_no_resume_still_credits_sponsor_status(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with db.cursor(db_path) as conn:
        conn.execute(
            "INSERT INTO sponsors (kvk, name, name_normalized, fetched_at) VALUES (?, ?, ?, ?)",
            ("31047344", "Booking.com B.V.", normalize("Booking.com B.V."), "2026-10-01"),
        )

    ingest_jobs(
        [JobListing("Booking.com", "Engineer", None, "https://x/1", "test")], db_path=db_path
    )

    rescore_jobs(db_path=db_path)

    jobs = list_jobs(db_path=db_path)
    assert jobs[0].fit_score == 5.0


def test_rescore_jobs_backfills_experience_level_for_pre_migration_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with db.cursor(db_path) as conn:
        # Simulate a row inserted before experience_level existed: insert
        # directly, bypassing ingest_jobs (which always sets it now).
        conn.execute(
            "INSERT INTO jobs (company_name, title, url, source, fetched_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("Acme", "Senior Platform Engineer", "https://x/1", "test", "2026-10-01"),
        )

    rescore_jobs(db_path=db_path)

    jobs = list_jobs(db_path=db_path)
    assert jobs[0].experience_level == "senior"
