"""Tests for the JobFinder web UI."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobfinder import db
from jobfinder.sponsors.normalize import normalize
from jobfinder.web.app import create_app, get_db_path


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


def test_index_with_no_data_prompts_sync(tmp_path: Path) -> None:
    empty_db = tmp_path / "empty.db"
    with db.cursor(empty_db):
        pass
    test_app = create_app()
    test_app.dependency_overrides[get_db_path] = lambda: empty_db

    response = TestClient(test_app).get("/")

    assert response.status_code == 200
    assert "jf sync-sponsors" in response.text


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
