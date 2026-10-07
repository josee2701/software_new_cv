"""Date and date-range detection in Spanish and English CV text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

MONTHS: dict[str, int] = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12, "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
    "ago": 8, "sep": 9, "sept": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12, "jan": 1, "apr": 4,
    "aug": 8, "dec": 12,
}  # fmt: skip
_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))
_YEAR = r"(?:19|20)\d{2}"
SIDE = rf"(?:(?:0?[1-9]|1[0-2])\s*[/.\-]\s*{_YEAR}|\b(?:{_MONTH})\.?(?:\s+de)?\s+{_YEAR}|\b{_YEAR})"
PRESENT = (
    r"(?:la\s+actualidad|actualidad|actualmente|actual|presente|present|current|now|today|"
    r"hoy|la\s+fecha|en\s+curso|in\s+progress)"
)
_RANGE_RE = re.compile(
    rf"(?P<start>{SIDE})\s*(?:–|—|-|\ba\b|\bal\b|hasta|\bto\b|until)\s*(?P<end>{SIDE}|{PRESENT}\b)",
    re.I,
)
_SIDE_RE = re.compile(SIDE, re.I)
_PRESENT_RE = re.compile(rf"^{PRESENT}$", re.I)
_NUMERIC_RE = re.compile(rf"(\d{{1,2}})\s*[/.\-]\s*({_YEAR})")
_NAMED_RE = re.compile(rf"({_MONTH})\.?(?:\s+de)?\s+({_YEAR})", re.I)


@dataclass(frozen=True)
class DateRange:
    start: date | None
    end: date | None
    current: bool
    confidence: float
    span: tuple[int, int]


def parse_side(text: str) -> tuple[date, float] | None:
    """One date: ``03/2021`` (0.95), ``marzo de 2021`` / ``Mar 2021`` (0.9), ``2021`` (0.7)."""
    text = text.strip()
    if m := _NUMERIC_RE.fullmatch(text):
        month, year = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1), 0.95
        return None
    if m := _NAMED_RE.fullmatch(text):
        return date(int(m.group(2)), MONTHS[m.group(1).lower()], 1), 0.9
    if re.fullmatch(_YEAR, text):
        return date(int(text), 1, 1), 0.7
    return None


def find_range(text: str) -> DateRange | None:
    match = _RANGE_RE.search(text)
    if match is None:
        return None
    start = parse_side(match.group("start"))
    if start is None:
        return None
    end_text = match.group("end")
    if _PRESENT_RE.match(end_text.strip()):
        return DateRange(start[0], None, True, start[1], match.span())
    end = parse_side(end_text)
    if end is None or end[0] < start[0]:
        return None
    return DateRange(start[0], end[0], False, min(start[1], end[1]), match.span())


def find_date(text: str) -> tuple[date, float, tuple[int, int]] | None:
    """First single date in ``text`` (for certifications)."""
    for match in _SIDE_RE.finditer(text):
        parsed = parse_side(match.group(0))
        if parsed is not None:
            return parsed[0], parsed[1], match.span()
    return None


def cut(text: str, span: tuple[int, int]) -> str:
    """``text`` without ``span`` (keeps both sides separated by a space)."""
    return f"{text[: span[0]]} {text[span[1] :]}"
