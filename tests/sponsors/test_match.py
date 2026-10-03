"""Tests for jobfinder.sponsors.match."""

from __future__ import annotations

from pathlib import Path

import pytest

from jobfinder import db
from jobfinder.sponsors.match import match_company
from jobfinder.sponsors.normalize import normalize


@pytest.fixture
def seeded_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    with db.cursor(db_path) as conn:
        for kvk, name in [
            ("31047344", "Booking.com B.V."),
            ("83892869", "@EasePay B.V."),
            ("17052456", "ASML Netherlands B.V."),
            # Real companies from the live register, used below to pin down
            # a false-positive regression found during manual verification.
            ("62280708", "Joulz Infradiensten B.V."),
            ("30132076", "Wink B.V."),
        ]:
            conn.execute(
                "INSERT INTO sponsors (kvk, name, name_normalized, fetched_at) VALUES (?, ?, ?, ?)",
                (kvk, name, normalize(name), "2026-10-01T00:00:00"),
            )
    return db_path


def test_match_company_finds_match_despite_legal_suffix(seeded_db: Path) -> None:
    result = match_company("Booking.com", db_path=seeded_db)
    assert result.is_sponsor is True
    assert result.kvk == "31047344"


def test_match_company_finds_match_despite_stray_leading_symbol(seeded_db: Path) -> None:
    result = match_company("EasePay", db_path=seeded_db)
    assert result.is_sponsor is True
    assert result.kvk == "83892869"


def test_match_company_finds_abbreviated_official_name(seeded_db: Path) -> None:
    result = match_company("ASML", db_path=seeded_db)
    assert result.is_sponsor is True
    assert result.kvk == "17052456"


def test_match_company_rejects_unrelated_name(seeded_db: Path) -> None:
    result = match_company("Totally Unrelated Bakery XYZ", db_path=seeded_db)
    assert result.is_sponsor is False


@pytest.mark.parametrize(
    "unrelated_query",
    [
        # Regression: live spot-check found WRatio scored both of these at
        # a false-positive 90.0 against real register entries (it falls
        # back to partial_ratio * 0.9, which a short query trivially
        # satisfies against almost any longer candidate). token_set_ratio
        # must keep rejecting them.
        "Adien",
        "Jansen Fietsenwinkel Zoetermeer",
    ],
)
def test_match_company_rejects_short_unrelated_query_against_long_candidate(
    seeded_db: Path, unrelated_query: str
) -> None:
    result = match_company(unrelated_query, db_path=seeded_db)
    assert result.is_sponsor is False


def test_match_company_raises_on_empty_table(tmp_path: Path) -> None:
    empty_db_path = tmp_path / "empty.db"
    with db.cursor(empty_db_path):
        pass  # just create the schema, no rows

    with pytest.raises(RuntimeError, match="sync-sponsors"):
        match_company("Booking.com", db_path=empty_db_path)
