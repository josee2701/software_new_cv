"""Shared interface between ``validator/`` and ``export/`` (owned by the lead; see DECISIONS.md).

Rules are pure functions ``(RuleContext) -> list[Hit]``. The engine turns hits into
``Finding`` objects, assigning ``rule_id`` and the severity for the profile destination
declared in the ``@rule`` decorator. Do not change these types without lead approval.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from models.enums import Destination, Severity
from schemas import ExportProfileOut, ResumeOut


class Phase(StrEnum):
    PRE = "pre"  # needs only cv/profile (+ optional html/pages from the renderer)
    POST = "post"  # needs the generated PDF (technical.*)


@dataclass(frozen=True)
class Hit:
    """What a rule reports. Severity and rule id are added by the engine."""

    message: str
    section: str | None = None
    entity: str | None = None  # experience | achievement | education | skill_category | ...
    entity_id: int | None = None
    suggestion: str | None = None


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    message: str
    section: str | None = None
    entity: str | None = None
    entity_id: int | None = None
    suggestion: str | None = None


@dataclass(frozen=True)
class PdfInfo:
    """Produced by ``export/verify.py`` from a generated PDF (spec §9.3)."""

    pages: int
    coverage: float  # |tokens_cv ∩ tokens_pdf| / |tokens_cv|
    has_text: bool
    email_found: bool
    phone_found: bool  # compared on digits only (see RENDER_CONTEXT.md)
    fonts: tuple[str, ...] = ()
    fonts_embedded: bool = True
    non_latin1_chars: tuple[str, ...] = ()  # outside Latin-1 + common symbols (•, –, —, ·)
    missing_tokens: tuple[str, ...] = ()  # first 20
    title: str | None = None
    author: str | None = None
    filename: str | None = None


@dataclass(frozen=True)
class RuleContext:
    cv: ResumeOut
    profile: ExportProfileOut
    html: str | None = None  # final rendered HTML (structure.no_tables, single_column)
    pages: int | None = None  # rendered page count (length.*); None if not rendered yet
    pdf: PdfInfo | None = None  # only for Phase.POST rules

    @property
    def destination(self) -> Destination:
        return self.profile.destination


@dataclass(frozen=True)
class Report:
    score: int  # 0..100
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity is Severity.ERROR)

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings if f.severity is Severity.WARNING)

    def blocks_export(self, destination: Destination) -> bool:
        """ATS exports are blocked by any error; mail never blocks (spec §9.1)."""
        return destination is Destination.ATS and self.errors > 0


RuleFn = Callable[[RuleContext], list[Hit]]
