"""Text lines with layout hints, the common input of the sectionizer and parsers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    text: str
    size: float = 0.0  # font size (pt); 0 if unknown
    bold: bool = False  # most of the line is bold (or a heading style in DOCX)
    x0: float = 0.0  # left position (pt) / indentation
    page: int = 0
    column: str = "main"  # "main" | "side" (two-column layouts)
    style: str = ""  # DOCX paragraph style ("Title", "Heading 1", "List Bullet"…)
    bullet: bool = False  # DOCX list paragraph
