"""Import a PDF/DOCX resume into an editable ``ImportPreview`` (spec §11)."""

from __future__ import annotations

from importer.docx_importer import docx_lines
from importer.parsers import build_preview
from importer.pdf_importer import pdf_lines
from schemas.importer import ImportPreview


class ImportFormatError(ValueError):
    """The uploaded file is neither a PDF nor a DOCX."""


def detect_format(data: bytes, filename: str | None = None) -> str:
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK") and (filename is None or filename.lower().endswith(".docx")):
        return "docx"
    raise ImportFormatError("Formato no soportado: sube un PDF o un DOCX")


def parse_document(data: bytes, filename: str | None = None) -> ImportPreview:
    """Parse a PDF or DOCX without writing anything."""
    source = detect_format(data, filename)
    lines = pdf_lines(data) if source == "pdf" else docx_lines(data)
    return build_preview(lines, source=source, filename=filename)


__all__ = ["ImportFormatError", "detect_format", "parse_document"]
