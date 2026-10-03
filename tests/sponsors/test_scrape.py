"""Tests for jobfinder.sponsors.scrape."""

from __future__ import annotations

from pathlib import Path

import pytest

from jobfinder import db
from jobfinder.sponsors import scrape

FIXTURE_HTML = (
    Path(__file__).resolve().parent.parent / "fixtures" / "ind_sponsors_sample.html"
).read_text()


def test_parse_extracts_all_rows() -> None:
    rows = scrape.parse(FIXTURE_HTML)
    assert len(rows) == 5
    assert {r.kvk for r in rows} == {"16051874", "17037842", "83892869", "82701695", "31047344"}


def test_parse_keeps_raw_name_and_whitespace_normalized() -> None:
    rows = scrape.parse(FIXTURE_HTML)
    booking = next(r for r in rows if r.kvk == "31047344")
    assert booking.name == "Booking.com B.V."


def test_parse_populates_normalized_name() -> None:
    rows = scrape.parse(FIXTURE_HTML)
    for row in rows:
        assert row.name_normalized
        assert row.name_normalized == row.name_normalized.lower()


def test_fetch_sponsors_raises_when_zero_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scrape, "fetch_html", lambda: "<table></table>")
    with pytest.raises(RuntimeError, match="zero sponsors"):
        scrape.fetch_sponsors()


def test_fetch_sponsors_returns_parsed_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scrape, "fetch_html", lambda: FIXTURE_HTML)
    rows = scrape.fetch_sponsors()
    assert len(rows) == 5


def test_sync_sponsors_upserts_into_db(monkeypatch: pytest.MonkeyPatch, dsn: str) -> None:
    monkeypatch.setattr(scrape, "fetch_html", lambda: FIXTURE_HTML)

    count = scrape.sync_sponsors(dsn=dsn)

    assert count == 5
    with db.cursor(dsn) as conn:
        stored = conn.execute("SELECT COUNT(*) AS c FROM sponsors").fetchone()["c"]
    assert stored == 5


def test_sync_sponsors_is_idempotent_on_rerun(monkeypatch: pytest.MonkeyPatch, dsn: str) -> None:
    monkeypatch.setattr(scrape, "fetch_html", lambda: FIXTURE_HTML)

    scrape.sync_sponsors(dsn=dsn)
    second_count = scrape.sync_sponsors(dsn=dsn)

    assert second_count == 5
    with db.cursor(dsn) as conn:
        stored = conn.execute("SELECT COUNT(*) AS c FROM sponsors").fetchone()["c"]
    assert stored == 5


def test_sync_sponsors_collapses_duplicate_kvk_in_source(
    monkeypatch: pytest.MonkeyPatch, dsn: str
) -> None:
    """The live IND register has been seen to list the same KVK twice; the
    returned count should reflect distinct sponsors stored, not raw rows
    parsed off the page."""
    html_with_duplicate = """
    <table><tbody>
    <tr><th scope="row">Booking.com B.V.</th><td>31047344</td></tr>
    <tr><th scope="row">Booking.com Netherlands B.V.</th><td>31047344</td></tr>
    </tbody></table>
    """
    monkeypatch.setattr(scrape, "fetch_html", lambda: html_with_duplicate)

    count = scrape.sync_sponsors(dsn=dsn)

    assert count == 1
    with db.cursor(dsn) as conn:
        stored = conn.execute("SELECT COUNT(*) AS c FROM sponsors").fetchone()["c"]
    assert stored == 1
