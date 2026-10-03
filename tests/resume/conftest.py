"""Shared fixtures for resume-parsing tests: real, generated PDFs.

Using actual PDF files (via reportlab) rather than mocking pdfplumber -
the whole point of these tests is verifying the real PDF-parsing
integration, not just our own code around it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


@pytest.fixture
def text_pdf(tmp_path: Path) -> Path:
    """A real single-page PDF with a genuine, selectable text layer."""
    path = tmp_path / "resume.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    lines = [
        "Jane Doe",
        "Senior Backend Engineer",
        "",
        "2019 - 2023   Backend Engineer, Acme Corp",
        "2023 - Present   Staff Engineer, Example Inc",
        "",
        "Skills: Python, Kubernetes, Terraform, PostgreSQL",
        "",
        "MSc Computer Science, University of Somewhere",
    ]
    y = 750
    for line in lines:
        c.drawString(72, y, line)
        y -= 18
    c.save()
    return path


@pytest.fixture
def scanned_pdf(tmp_path: Path) -> Path:
    """A real PDF with NO text layer - an image embedded on an otherwise
    empty page, structurally the same as a scanned/photographed resume."""
    image_path = tmp_path / "page.png"
    image = Image.new("RGB", (850, 1100), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((50, 50), "Jane Doe - Senior Backend Engineer", fill="black")
    draw.text((50, 90), "Skills: Python, Kubernetes", fill="black")
    image.save(image_path)

    pdf_path = tmp_path / "scanned.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawImage(str(image_path), 0, 0, width=612, height=792)
    c.save()
    return pdf_path
