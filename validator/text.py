"""Text helpers for rules: accent folding, tokens, word lists (verbs, pronouns)."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
_WORD_RE = re.compile(r"[^\W_]+")
_COMMENT_RE = re.compile(r"/\*.*?\*/|<!--.*?-->", re.DOTALL)

# First person in the summary (content.summary_first_person). Past-tense verbs in first person
# ("Lideré") are not pronouns (DECISIONS.md).
SUMMARY_PRONOUNS: dict[str, frozenset[str]] = {
    "es": frozenset({"yo", "mi", "mis", "me", "conmigo", "mio", "mia", "mios", "mias"}),
    "en": frozenset({"i", "my", "me", "mine", "myself", "im", "ive", "id", "ill"}),
}
# Pronouns in achievements (content.no_pronouns).
ACHIEVEMENT_PRONOUNS: dict[str, frozenset[str]] = {
    "es": frozenset(
        {
            "yo",
            "mi",
            "mis",
            "nosotros",
            "nosotras",
            "nuestro",
            "nuestra",
            "nuestros",
            "nuestras",
        }
    ),
    "en": frozenset({"i", "my", "we", "our", "ours", "myself", "ourselves"}),
}


def fold(text: str) -> str:
    """Lowercase without accents: ``"Lideré"`` → ``"lidere"``, ``"Año"`` → ``"ano"``."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def words(text: str) -> list[str]:
    """Folded words (letters and digits); apostrophes split nothing: ``"I'm"`` → ``["im"]``."""
    return _WORD_RE.findall(fold(text).replace("'", "").replace("\u2019", ""))


def first_word(text: str) -> str:
    """First alphabetic word, folded (``"• Lideré la..."`` → ``"lidere"``)."""
    match = re.search(r"[^\W\d_]+", fold(text))
    return match.group(0) if match else ""


def strip_comments(source: str) -> str:
    """Remove CSS ``/* */`` and HTML ``<!-- -->`` comments."""
    return _COMMENT_RE.sub(" ", source)


def lang_or_default(lang: str) -> str:
    return lang if lang in ("es", "en") else "es"


def _read_words(path: Path) -> frozenset[str]:
    result: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        content = line.split("#", 1)[0]
        result.update(fold(token) for token in content.split())
    return frozenset(result)


@lru_cache
def action_verbs(lang: str) -> frozenset[str]:
    """Folded verb forms from ``validator/data/verbs_{lang}.txt`` (one verb per line)."""
    return _read_words(DATA_DIR / f"verbs_{lang_or_default(lang)}.txt")


def verb_lines(lang: str) -> list[list[str]]:
    """Lines of the verb file (one verb per line: its forms). Used by tests/docs."""
    path = DATA_DIR / f"verbs_{lang_or_default(lang)}.txt"
    rows = [line.split("#", 1)[0].split() for line in path.read_text(encoding="utf-8").splitlines()]
    return [row for row in rows if row]


class _TextExtractor(HTMLParser):
    """Visible text of an HTML document (skips ``<style>``, ``<script>``, ``<head>``)."""

    _HIDDEN = frozenset({"style", "script", "head", "title"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._HIDDEN:
            self._hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._HIDDEN and self._hidden:
            self._hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self.parts.append(data)


def html_text(html: str) -> str:
    """Visible text of ``html`` with whitespace collapsed."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return " ".join(" ".join(parser.parts).split())


class _AnchorExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.anchors.append((self._href, " ".join("".join(self._text).split())))
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)


def html_anchors(html: str) -> list[tuple[str, str]]:
    """``[(href, visible_text), ...]`` for every ``<a>`` in ``html``."""
    parser = _AnchorExtractor()
    parser.feed(html)
    parser.close()
    return parser.anchors
