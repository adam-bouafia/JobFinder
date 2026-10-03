"""Export stored jobs to Markdown, plain text, or PDF."""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from .ingest import StoredJob

SUPPORTED_FORMATS = ("md", "txt", "pdf")


def _tags(job: StoredJob) -> list[str]:
    tags = []
    if job.fit_score is not None:
        tags.append(f"fit {job.fit_score:.1f}")
    if job.sponsor_kvk:
        tags.append(f"IND sponsor (KVK {job.sponsor_kvk})")
    if job.is_open_application:
        tags.append("open application")
    tags.append(job.source)
    return tags


def to_markdown(jobs: list[StoredJob]) -> str:
    lines = ["# JobFinder export", "", f"{len(jobs)} job(s)", ""]
    for job in jobs:
        lines.append(f"## {job.title}")
        company_line = f"**{job.company_name}**"
        if job.location:
            company_line += f" &middot; {job.location}"
        lines.append(company_line)
        lines.append("")
        lines.append(" &middot; ".join(_tags(job)))
        lines.append("")
        lines.append(f"[View posting]({job.url})")
        lines.append("")
    return "\n".join(lines)


def to_text(jobs: list[StoredJob]) -> str:
    blocks = []
    for job in jobs:
        lines = [f"{job.title} - {job.company_name}"]
        if job.location:
            lines.append(f"Location: {job.location}")
        lines.append(", ".join(_tags(job)))
        lines.append(job.url)
        blocks.append("\n".join(lines))
    header = f"JobFinder export - {len(jobs)} job(s)\n{'=' * 40}\n"
    return header + "\n\n".join(blocks) + "\n"


def to_pdf_bytes(jobs: list[StoredJob]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 0.75 * inch
    y = height - margin

    def new_page() -> None:
        nonlocal y
        pdf.showPage()
        y = height - margin
        pdf.setFont("Helvetica", 9)

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(margin, y, "JobFinder export")
    y -= 20
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margin, y, f"{len(jobs)} job(s)")
    y -= 24

    for job in jobs:
        if y < margin + 60:
            new_page()
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin, y, job.title[:90])
        y -= 14
        pdf.setFont("Helvetica", 9)
        company_line = job.company_name + (f" - {job.location}" if job.location else "")
        pdf.drawString(margin, y, company_line[:100])
        y -= 12
        pdf.drawString(margin, y, " | ".join(_tags(job))[:100])
        y -= 12
        pdf.setFillColorRGB(0.2, 0.2, 0.6)
        pdf.drawString(margin, y, job.url[:100])
        pdf.setFillColorRGB(0, 0, 0)
        y -= 20

    pdf.save()
    return buffer.getvalue()


def export_jobs(jobs: list[StoredJob], path: Path) -> None:
    """Write `jobs` to `path`; format is inferred from the file extension."""
    suffix = path.suffix.lower().lstrip(".")
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported export format {suffix!r} - use one of {SUPPORTED_FORMATS}")
    if suffix == "md":
        path.write_text(to_markdown(jobs))
    elif suffix == "txt":
        path.write_text(to_text(jobs))
    else:
        path.write_bytes(to_pdf_bytes(jobs))
