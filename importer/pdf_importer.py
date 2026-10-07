"""PDF → lines (pdfplumber words with position, size and bold), column-aware."""

from __future__ import annotations

import io
from typing import Any

import pdfplumber

from importer.lines import Line

_LINE_TOLERANCE = 3.0
_MIN_GAP = 12  # pt of empty vertical band between two columns
_BOLD_RATIO = 0.6


def _columns(words: list[dict[str, Any]], width: float) -> list[list[dict[str, Any]]]:
    """Split a page in two columns when an empty vertical band separates the words."""
    if len(words) < 20:
        return [words]
    covered = [False] * (int(width) + 2)
    for word in words:
        for x in range(max(0, int(word["x0"])), min(len(covered), int(word["x1"]) + 1)):
            covered[x] = True
    lo, hi = int(width * 0.15), int(width * 0.7)
    best: tuple[int, int] | None = None
    run_start: int | None = None
    for x in range(lo, hi + 1):
        if not covered[x]:
            run_start = x if run_start is None else run_start
            if best is None or x - run_start > best[1] - best[0]:
                best = (run_start, x)
        else:
            run_start = None
    if best is None or best[1] - best[0] < _MIN_GAP:
        return [words]
    split = (best[0] + best[1]) / 2
    left = [w for w in words if w["x1"] <= split]
    right = [w for w in words if w["x1"] > split]
    if min(len(left), len(right)) < 0.12 * len(words):
        return [words]
    return [left, right]


def _lines(words: list[dict[str, Any]], page: int, column: str) -> list[Line]:
    result: list[Line] = []
    group: list[dict[str, Any]] = []

    def flush() -> None:
        if not group:
            return
        ordered = sorted(group, key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in ordered)
        total = sum(len(w["text"]) for w in ordered) or 1
        bold = sum(len(w["text"]) for w in ordered if "bold" in str(w["fontname"]).lower())
        result.append(
            Line(
                text=text,
                size=round(max(float(w["size"]) for w in ordered), 1),
                bold=bold / total >= _BOLD_RATIO,
                x0=round(min(float(w["x0"]) for w in ordered), 1),
                page=page,
                column=column,
            )
        )
        group.clear()

    for word in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if group and abs(word["top"] - group[0]["top"]) > _LINE_TOLERANCE:
            flush()
        group.append(word)
    flush()
    return result


def pdf_lines(data: bytes) -> list[Line]:
    """Lines in reading order. Two-column pages: the column with more words is "main"."""
    lines: list[Line] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for number, page in enumerate(pdf.pages):
            words = page.extract_words(extra_attrs=["size", "fontname"])
            columns = _columns(words, float(page.width))
            if len(columns) == 1:
                lines += _lines(columns[0], number, "main")
                continue
            main = 0 if len(columns[0]) >= len(columns[1]) else 1
            for index, column in enumerate(columns):
                lines += _lines(column, number, "main" if index == main else "side")
    return lines
