"""Tests for the JobFinder web UI."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from jobfinder import db
from jobfinder.jobs import adzuna
from jobfinder.jobs.ingest import ingest_jobs
from jobfinder.jobs.models import JobListing
from jobfinder.sponsors.normalize import normalize
from jobfinder.web.app import create_app, get_db_path


def _sample_resume_pdf(text: str) -> bytes:
    """A minimal real PDF with a text layer, for upload tests - pdfplumber
    needs an actual parseable PDF, not just arbitrary bytes."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.drawString(72, 700, text)
    pdf.save()
    return buffer.getvalue()


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    with db.cursor(db_path) as conn:
        for kvk, name in [
            ("31047344", "Booking.com B.V."),
            ("17052456", "ASML Netherlands B.V."),
        ]:
            conn.execute(
                "INSERT INTO sponsors (kvk, name, name_normalized, fetched_at) VALUES (?, ?, ?, ?)",
                (kvk, name, normalize(name), "2026-10-01T00:00:00"),
            )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('ind_synced_at', ?)",
            ("2026-10-01T00:00:00",),
        )

    test_app = create_app()
    test_app.dependency_overrides[get_db_path] = lambda: db_path
    return TestClient(test_app)


def test_index_shows_sponsor_count(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "2 recognised sponsors synced" in response.text


def test_index_with_no_sponsor_data_prompts_sync(tmp_path: Path) -> None:
    empty_db = tmp_path / "empty.db"
    with db.cursor(empty_db):
        pass
    test_app = create_app()
    test_app.dependency_overrides[get_db_path] = lambda: empty_db

    response = TestClient(test_app).get("/")

    assert response.status_code == 200
    assert "jf sync-sponsors" in response.text


def test_company_page_shows_sponsor_count(client: TestClient) -> None:
    response = client.get("/company")
    assert response.status_code == 200
    assert "2 recognised sponsors synced" in response.text
    assert "Check a Company" in response.text


def test_search_finds_known_sponsor(client: TestClient) -> None:
    response = client.get("/search", params={"company": "Booking.com"})
    assert response.status_code == 200
    assert "Recognised sponsor" in response.text
    assert "31047344" in response.text


def test_search_rejects_unrelated_name(client: TestClient) -> None:
    response = client.get("/search", params={"company": "Totally Unrelated Bakery XYZ"})
    assert response.status_code == 200
    assert "Not found" in response.text


def test_search_with_empty_query_shows_nothing(client: TestClient) -> None:
    response = client.get("/search", params={"company": "  "})
    assert response.status_code == 200
    assert response.text.strip() == ""


def test_static_htmx_is_served(client: TestClient) -> None:
    response = client.get("/static/htmx.min.js")
    assert response.status_code == 200
    assert "htmx" in response.text.lower()


@pytest.fixture
def client_with_jobs(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    with db.cursor(db_path) as conn:
        conn.execute(
            "INSERT INTO sponsors (kvk, name, name_normalized, fetched_at) VALUES (?, ?, ?, ?)",
            ("31047344", "Booking.com B.V.", normalize("Booking.com B.V."), "2026-10-01T00:00:00"),
        )
    ingest_jobs(
        [
            JobListing(
                "Booking.com",
                "Senior Backend Engineer",
                "Amsterdam",
                "https://x/1",
                "test",
                description="Own our payments backend.",
            ),
            JobListing("Unrelated Co", "General Application", None, "https://x/2", "test"),
        ],
        db_path=db_path,
    )

    test_app = create_app()
    test_app.dependency_overrides[get_db_path] = lambda: db_path
    return TestClient(test_app)


def test_index_lists_jobs_by_default(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/")
    assert response.status_code == 200
    assert "Senior Backend Engineer" in response.text
    assert "Booking.com" in response.text
    assert "2 jobs found" in response.text


def test_index_shows_job_description(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/")
    assert "Own our payments backend." in response.text


def test_index_with_no_jobs_shows_empty_state(tmp_path: Path) -> None:
    empty_db = tmp_path / "empty.db"
    with db.cursor(empty_db):
        pass
    test_app = create_app()
    test_app.dependency_overrides[get_db_path] = lambda: empty_db

    response = TestClient(test_app).get("/")

    assert response.status_code == 200
    assert "No jobs match" in response.text


def test_results_partial_filters_by_sponsors_only(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/results", params={"sponsors_only": "true"})
    assert response.status_code == 200
    assert "Senior Backend Engineer" in response.text
    assert "General Application" not in response.text


def test_results_partial_filters_by_open_applications_only(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/results", params={"open_applications_only": "true"})
    assert response.status_code == 200
    assert "General Application" in response.text
    assert "Senior Backend Engineer" not in response.text


def test_results_partial_filters_by_experience(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/results", params={"experience": "senior"})
    assert response.status_code == 200
    assert "Senior Backend Engineer" in response.text
    assert "General Application" not in response.text


def test_results_partial_filters_by_free_text_query(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/results", params={"query": "backend"})
    assert response.status_code == 200
    assert "Senior Backend Engineer" in response.text
    assert "General Application" not in response.text


def test_results_partial_is_just_the_fragment_not_a_full_page(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/results")
    assert "<html" not in response.text
    assert "<nav>" not in response.text


def test_export_markdown(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/export", params={"format": "md"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert "Senior Backend Engineer" in response.text


def test_export_text(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/export", params={"format": "txt"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "Senior Backend Engineer" in response.text


def test_export_pdf(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/export", params={"format": "pdf"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_export_respects_filters(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/export", params={"format": "md", "sponsors_only": "true"})
    assert "Senior Backend Engineer" in response.text
    assert "General Application" not in response.text


def test_export_respects_query(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/export", params={"format": "md", "query": "general"})
    assert "General Application" in response.text
    assert "Senior Backend Engineer" not in response.text


def test_export_rejects_unknown_format(client_with_jobs: TestClient) -> None:
    response = client_with_jobs.get("/export", params={"format": "docx"})
    assert response.status_code == 400


def test_resume_page_with_no_resume_prompts_upload(client: TestClient) -> None:
    response = client.get("/resume")
    assert response.status_code == 200
    assert "No resume uploaded yet" in response.text


def test_resume_upload_rejects_non_pdf(client: TestClient) -> None:
    response = client.post(
        "/resume/upload",
        files={"file": ("resume.txt", b"plain text", "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/resume?error=")


def test_resume_upload_parses_pdf_and_rescores_jobs(
    client_with_jobs: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("jobfinder.web.app.RESUME_DIR", tmp_path / "resumes")
    pdf_bytes = _sample_resume_pdf("Experienced Python backend engineer.")

    upload = client_with_jobs.post(
        "/resume/upload",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
        follow_redirects=False,
    )
    assert upload.status_code == 303
    assert upload.headers["location"] == "/resume?uploaded=true"

    page = client_with_jobs.get("/resume")
    assert "python" in page.text.lower()

    index = client_with_jobs.get("/")
    assert "uploaded resume" in index.text


def test_jobs_fetch_without_credentials_redirects_with_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)

    response = client.post("/jobs/fetch", data={"query": "engineer"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/?error=")


def test_jobs_fetch_ingests_new_listings(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_listing = JobListing("Acme", "Platform Engineer", "Amsterdam", "https://x/9", "adzuna")
    monkeypatch.setattr(adzuna, "search", lambda query, **kwargs: [fake_listing])

    response = client.post("/jobs/fetch", data={"query": "platform"}, follow_redirects=False)

    assert response.status_code == 303
    assert "fetched=1" in response.headers["location"]

    index = client.get("/")
    assert "Platform Engineer" in index.text
