"""Tests for jobfinder.resume.extract."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from jobfinder.resume.extract import extract_text, extract_text_layer

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None


def test_extract_text_layer_reads_real_text_pdf(text_pdf: Path) -> None:
    pages = extract_text_layer(text_pdf)
    assert len(pages) == 1
    assert "Jane Doe" in pages[0]
    assert "Backend Engineer" in pages[0]


def test_extract_text_layer_returns_empty_string_for_image_only_pdf(scanned_pdf: Path) -> None:
    pages = extract_text_layer(scanned_pdf)
    assert len(pages) == 1
    assert pages[0].strip() == ""


def test_extract_text_uses_text_layer_when_present(text_pdf: Path) -> None:
    pages = extract_text(text_pdf)
    assert "Jane Doe" in pages[0]


@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract binary not installed")
def test_extract_text_falls_back_to_ocr_for_scanned_page(scanned_pdf: Path) -> None:
    pages = extract_text(scanned_pdf)
    assert "Jane" in pages[0] or "Senior" in pages[0]
