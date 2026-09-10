"""Pure formatting helpers used by ``render.context`` (dates, URLs, phone, names)."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

MONTHS: dict[str, tuple[str, ...]] = {
    "es": ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
}
DASH = " – "  # en dash with spaces (contract)


def fmt_date(value: date | None, fmt: str, lang: str) -> str:
    """``MM/YYYY`` → "03/2024"; ``MMM YYYY`` → "mar 2024" / "Mar 2024"; ``YYYY`` → "2024"."""
    if value is None:
        return ""
    if fmt == "YYYY":
        return f"{value.year}"
    if fmt == "MMM YYYY":
        months = MONTHS.get(lang, MONTHS["en"])
        return f"{months[value.month - 1]} {value.year}"
    return f"{value.month:02d}/{value.year}"


def fmt_range(
    start: date | None,
    end: date | None,
    *,
    fmt: str,
    lang: str,
    open_label: str | None = None,
) -> str:
    """Date range. ``open_label`` ("Actual", "En curso"…) replaces a missing end date."""
    first, last = fmt_date(start, fmt, lang), fmt_date(end, fmt, lang)
    if open_label and not last:
        return f"{first}{DASH}{open_label}" if first else open_label
    if first and last:
        return first if first == last else f"{first}{DASH}{last}"
    return first or last


def url_display(url: str | None) -> str:
    """URL without scheme, ``www.`` or trailing "/" (``https://www.x.com/a/`` → ``x.com/a``)."""
    if not url:
        return ""
    text = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", "", url.strip())
    text = re.sub(r"^www\.", "", text)
    return text.rstrip("/")


# Calling codes used to split an E.164 number for display.
_CALLING_CODES = sorted(
    {
        "1",
        "7",
        "33",
        "34",
        "39",
        "44",
        "49",
        "51",
        "52",
        "53",
        "54",
        "55",
        "56",
        "57",
        "58",
        "351",
        "502",
        "503",
        "504",
        "505",
        "506",
        "507",
        "591",
        "593",
        "595",
        "598",
    },
    key=len,
    reverse=True,
)


def _group(digits: str) -> str:
    if len(digits) == 10:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    if len(digits) == 9:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    if len(digits) == 8:
        return f"{digits[:4]} {digits[4:]}"
    if len(digits) == 7:
        return f"{digits[:3]} {digits[3:]}"
    return " ".join(digits[i : i + 3] for i in range(0, len(digits), 3))


def phone_display(phone: str) -> str:
    """ "+573001234567" → "+57 300 123 4567". Non-E.164 input is returned unchanged."""
    if not re.fullmatch(r"\+\d{8,15}", phone or ""):
        return phone or ""
    digits = phone[1:]
    for code in _CALLING_CODES:
        if digits.startswith(code):
            return f"+{code} {_group(digits[len(code) :])}"
    return phone


_PARTICLES = {"de", "del", "la", "las", "los", "y", "da", "das", "do", "dos", "van", "von"}


def _name_units(full_name: str) -> list[list[str]]:
    """Group words into units: particles ("de", "la"…) join the following word."""
    units: list[list[str]] = []
    pending: list[str] = []
    for word in full_name.split():
        pending.append(word)
        if word.lower() not in _PARTICLES:
            units.append(pending)
            pending = []
    if pending:  # trailing particles with nothing after them
        if units:
            units[-1].extend(pending)
        else:
            units.append(pending)
    return units


def _unit_letter(unit: list[str]) -> str:
    """First alphabetic letter of the unit, skipping its particles (accents kept)."""
    words = [w for w in unit if w.lower() not in _PARTICLES] or unit
    for char in "".join(words):
        if char.isalpha():
            return char.upper()
    return ""


def initials(full_name: str) -> str:
    """Monogram initials (lead's rule, docs/DECISIONS.md).

    Particles join the next word into one unit. 1 unit → its letter; 2–3 units → units 0 and 1
    ("Santiago Restrepo Mejía" → "SR"); 4+ units → units 0 and 2
    ("Andrés Felipe Rojas Martínez" → "AR", "Juan de la Cruz Gómez Ruiz" → "JG").
    """
    units = _name_units(full_name)
    if not units:
        return ""
    if len(units) == 1:
        return _unit_letter(units[0])
    second = units[1] if len(units) <= 3 else units[2]
    return _unit_letter(units[0]) + _unit_letter(second)


def _ascii_slug(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^A-Za-z0-9]+", "_", plain).strip("_")


def file_stem(full_name: str) -> str:
    """``Nombre_Apellido`` for export file names: first given name + first surname
    (same unit rule as :func:`initials`), without accents or spaces."""
    units = _name_units(full_name)
    if not units:
        return ""
    first = next((w for w in units[0] if w.lower() not in _PARTICLES), units[0][0])
    parts = [first]
    if len(units) > 1:
        parts.append(" ".join(units[1] if len(units) <= 3 else units[2]))
    return "_".join(p for p in (_ascii_slug(x) for x in parts) if p)


def years_label(years: int | None, one: str, many: str) -> str | None:
    """``years_label(6, "1 año", "{n} años")`` → "6 años"; None stays None."""
    if years is None:
        return None
    return one if years == 1 else many.replace("{n}", str(years))
