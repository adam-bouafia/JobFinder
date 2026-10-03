"""Tests for jobfinder.sponsors.normalize."""

from __future__ import annotations

import pytest

from jobfinder.sponsors.normalize import normalize


@pytest.mark.parametrize(
    ("variant_a", "variant_b"),
    [
        ("Booking.com B.V.", "Booking.com"),
        ("@EasePay B.V.", "EasePay"),
        ("@Fentures B.V.", "Fentures"),
        ("ASML Holding N.V.", "ASML"),
        ("Coolblue B.V.", "coolblue"),
    ],
)
def test_normalize_treats_equivalent_spellings_as_equal(variant_a: str, variant_b: str) -> None:
    assert normalize(variant_a) == normalize(variant_b)


@pytest.mark.parametrize(
    "raw",
    [
        "Booking.com B.V.",
        "@EasePay B.V.",
        "Aa-Dee Machinefabriek en Staalbouw Nederland B.V.",
    ],
)
def test_normalize_is_lowercase_and_trimmed(raw: str) -> None:
    result = normalize(raw)
    assert result == result.lower()
    assert result == result.strip()
    assert result != ""


def test_normalize_distinguishes_different_companies() -> None:
    assert normalize("Booking.com B.V.") != normalize("Adyen N.V.")
