"""Tests for jobfinder.resume.parse."""

from __future__ import annotations

from pathlib import Path

from jobfinder.resume.parse import latest_resume_profile, parse_resume


def test_parse_resume_extracts_fields_from_a_real_pdf(text_pdf: Path, tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"

    profile = parse_resume(text_pdf, db_path=db_path)

    assert "python" in profile.skills
    assert "kubernetes" in profile.skills
    assert profile.years_experience is not None
    assert profile.years_experience > 0
    assert any("MSc" in line for line in profile.education)
    assert "Jane Doe" in profile.raw_text


def test_parse_resume_persists_and_is_retrievable(text_pdf: Path, tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"

    parse_resume(text_pdf, db_path=db_path)
    stored = latest_resume_profile(db_path=db_path)

    assert stored is not None
    assert stored.source_path == str(text_pdf)
    assert "python" in stored.skills


def test_latest_resume_profile_returns_none_when_nothing_parsed_yet(tmp_path: Path) -> None:
    from jobfinder import db

    db_path = tmp_path / "empty.db"
    with db.cursor(db_path):
        pass  # just create the schema

    assert latest_resume_profile(db_path=db_path) is None


def test_latest_resume_profile_returns_the_most_recent_one(tmp_path: Path) -> None:
    # Deliberately two plain text PDFs, not the scanned_pdf fixture: this
    # test is about insert-order/tiebreak logic, not the OCR path, and
    # shouldn't depend on tesseract being installed to pass.
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    def make_pdf(name: str, text: str) -> Path:
        path = tmp_path / name
        c = canvas.Canvas(str(path), pagesize=letter)
        c.drawString(72, 750, text)
        c.save()
        return path

    db_path = tmp_path / "test.db"
    first_pdf = make_pdf("first.pdf", "First Resume - more than twenty characters of real text")
    second_pdf = make_pdf("second.pdf", "Second Resume - more than twenty characters of real text")

    parse_resume(first_pdf, db_path=db_path)
    parse_resume(second_pdf, db_path=db_path)

    latest = latest_resume_profile(db_path=db_path)
    assert latest is not None
    assert latest.source_path == str(second_pdf)
