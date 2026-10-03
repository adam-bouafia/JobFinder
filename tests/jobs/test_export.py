"""Tests for jobfinder.jobs.export."""

from __future__ import annotations

from pathlib import Path

import pytest

from jobfinder.jobs.export import export_jobs, to_markdown, to_pdf_bytes, to_text
from jobfinder.jobs.ingest import StoredJob

SAMPLE_JOBS = [
    StoredJob(
        id=1,
        company_name="Booking.com",
        title="Backend Engineer",
        location="Amsterdam, Netherlands",
        url="https://example.com/job/1",
        source="greenhouse",
        is_open_application=False,
        sponsor_kvk="31047344",
        fit_score=6.0,
        experience_level="mid",
        fetched_at="2026-10-01T00:00:00",
    ),
    StoredJob(
        id=2,
        company_name="Unrelated Co",
        title="General Application",
        location=None,
        url="https://example.com/job/2",
        source="lever",
        is_open_application=True,
        sponsor_kvk=None,
        fit_score=None,
        experience_level=None,
        fetched_at="2026-10-01T00:00:00",
    ),
]


def test_to_markdown_includes_all_jobs_and_key_fields() -> None:
    md = to_markdown(SAMPLE_JOBS)
    assert "Backend Engineer" in md
    assert "Booking.com" in md
    assert "KVK 31047344" in md
    assert "General Application" in md
    assert "open application" in md
    assert "https://example.com/job/1" in md


def test_to_markdown_with_no_jobs_is_still_valid() -> None:
    md = to_markdown([])
    assert "0 job(s)" in md


def test_to_text_includes_all_jobs_and_key_fields() -> None:
    txt = to_text(SAMPLE_JOBS)
    assert "Backend Engineer - Booking.com" in txt
    assert "Amsterdam, Netherlands" in txt
    assert "https://example.com/job/2" in txt


def test_to_pdf_bytes_produces_a_real_pdf() -> None:
    pdf_bytes = to_pdf_bytes(SAMPLE_JOBS)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 500


@pytest.mark.parametrize("extension", ["md", "txt", "pdf"])
def test_export_jobs_writes_the_right_format(tmp_path: Path, extension: str) -> None:
    path = tmp_path / f"export.{extension}"

    export_jobs(SAMPLE_JOBS, path)

    assert path.exists()
    assert path.stat().st_size > 0


def test_export_jobs_rejects_an_unsupported_extension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported export format"):
        export_jobs(SAMPLE_JOBS, tmp_path / "export.docx")
