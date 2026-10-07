"""Text helpers shared by the importer parsers."""

from __future__ import annotations

import re
import unicodedata

EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:[a-z0-9][a-z0-9\-]*\.)+[a-z]{2,}(?:/[^\s|,;()<>·]*)?", re.I
)
PHONE_RE = re.compile(r"(?<![\w/])\+?\d[\d \-().]{6,}\d(?![\w/])")
PAGE_FOOTER_RE = re.compile(r"^(?:page|p[aá]gina)\s+\d+\s+(?:of|de)\s+\d+$", re.I)
_BULLET_RE = re.compile("^\\s*[•\\-*–·▪◦●○■□➢►‣\u2043]+\\s*")
_LABEL_RE = re.compile(r"^\s*([^:/]{2,40}?)\s*:\s*(\S.*)$")
_LIST_SPLIT_RE = re.compile(r"\s*(?:,|;|\||·|•|\s/\s)\s*")
PARTICLES = {"de", "del", "la", "las", "los", "y", "da", "das", "do", "dos", "van", "von", "en"}


def fold(text: str) -> str:
    """Lowercase without accents."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def collapse(text: str) -> str:
    return " ".join(text.split())


def is_bullet_text(text: str) -> bool:
    match = _BULLET_RE.match(text)
    return match is not None and bool(text[match.end() :].strip())


def strip_bullet(text: str) -> str:
    return collapse(_BULLET_RE.sub("", text, count=1))


def split_label(text: str) -> tuple[str, str] | None:
    """``"Tecnologías: Python, Go"`` → ``("Tecnologías", "Python, Go")``."""
    match = _LABEL_RE.match(text)
    if match is None:
        return None
    return collapse(match.group(1)), collapse(match.group(2))


def split_list(text: str) -> list[str]:
    """Split by ``, ; | · •`` and `` / `` (a bare "/" is kept: "CI/CD")."""
    items = (part.strip(" .") for part in _LIST_SPLIT_RE.split(text))
    return [item for item in items if item and len(item) <= 60]


def titlecase(text: str) -> str:
    words = text.split()
    return " ".join(
        w.lower() if i and w.lower() in PARTICLES else w[:1].upper() + w[1:].lower()
        for i, w in enumerate(words)
    )


def fix_case(text: str) -> tuple[str, bool]:
    """Title-case ALL-CAPS or badly mixed text; returns ``(text, changed)``."""
    words = [w for w in text.split() if any(c.isalpha() for c in w)]
    if not words:
        return text, False
    shouty = [w for w in words if len(w) > 3 and w.isupper() and "." not in w]
    lower = [w for w in words if w.islower() and w not in PARTICLES]
    if len(shouty) * 2 > len(words) or (shouty and lower):
        return titlecase(text), True
    return text, False


def normalize_url(url: str) -> str:
    url = url.strip().rstrip(".")
    return url if re.match(r"^https?://", url, re.I) else f"https://{url}"
