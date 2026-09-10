"""Validation: build ``ResumeOut`` + profile, run the engine and persist the report (spec §9).

``ValidationService(session).run_and_save(...)`` is used by the API and the CLI; the export
(Backend-Export) calls :func:`save_report` with a ``Report`` it already computed (full run with
html, pages and PDF). Module-level ``run_and_save``/``save_report`` take the session first.
"""

from __future__ import annotations

import logging

from jinja2 import TemplateNotFound
from sqlalchemy.orm import Session

from models import ValidationFinding, ValidationReport
from render.renderer import render
from schemas import ExportProfileOut, ResumeOut
from schemas.validation import ValidationReportOut
from services.base import TransactionalService
from services.errors import ConflictError, NotFoundError
from services.profile import ProfileService
from services.resume import ResumeService
from validator import engine
from validator.types import PdfInfo, Report, RuleContext

logger = logging.getLogger(__name__)


def _cut(value: str | None, size: int) -> str | None:
    if value is None or len(value) <= size:
        return value
    return value[: size - 1] + "…"


def _persist(
    session: Session, resume_id: int, profile_id: int | None, report: Report
) -> ValidationReport:
    """Add ``validation_report`` + ``validation_finding`` rows and flush (no commit)."""
    row = ValidationReport(
        resume_id=resume_id,
        profile_id=profile_id,
        score=max(0, min(100, report.score)),
        errors=report.errors,
        warnings=report.warnings,
    )
    row.findings = [
        ValidationFinding(
            rule_id=_cut(f.rule_id, 60) or "",
            severity=f.severity,
            message=_cut(f.message, 300) or "",
            section=_cut(f.section, 20),
            entity=_cut(f.entity, 30),
            entity_id=f.entity_id,
            suggestion=_cut(f.suggestion, 300),
        )
        for f in report.findings
    ]
    session.add(row)
    session.flush()
    session.refresh(row)
    return row


def count_pages(html: str) -> int | None:
    """Page count from ``export.pdf.count_pages`` (layout only, cached); None if unavailable."""
    try:
        from export.pdf import count_pages as _count
    except ImportError:  # pragma: no cover - export/ always ships count_pages
        return None
    try:
        return _count(html)
    except Exception:  # the PDF engine is optional for validation: rules skip pages
        logger.warning("No se pudo contar páginas del HTML", exc_info=True)
        return None


def render_for_validation(
    cv: ResumeOut, profile: ExportProfileOut, *, with_pages: bool = True
) -> tuple[str | None, int | None]:
    """Final HTML (not the preview) and its page count (None if it cannot be computed)."""
    try:
        result = render(cv, profile)
    except TemplateNotFound:
        return None, None
    pages = result.pages
    if pages is None and with_pages:
        pages = count_pages(result.html)
    return result.html, pages


class ValidationService(TransactionalService):
    # ------------------------------------------------------------------ inputs

    def load(
        self, resume_id: int, profile_id: int | None = None
    ) -> tuple[ResumeOut, ExportProfileOut]:
        """``ResumeOut`` and the profile (the first one of the resume if ``profile_id`` is None)."""
        cv = ResumeService(self.session).get_out(resume_id)
        if profile_id is not None:
            profile = ExportProfileOut.model_validate(
                ProfileService(self.session).get(profile_id, resume_id)
            )
            return cv, profile
        if not cv.profiles:
            raise ConflictError("El CV no tiene perfiles de exportación")
        return cv, cv.profiles[0]

    # ------------------------------------------------------------------ run + persist

    def run(
        self,
        resume_id: int,
        profile_id: int | None = None,
        *,
        html: str | None = None,
        pages: int | None = None,
        pdf: PdfInfo | None = None,
        render_html: bool = False,
    ) -> tuple[ExportProfileOut, Report]:
        """Run the engine without persisting. ``render_html`` renders the HTML if not given."""
        cv, profile = self.load(resume_id, profile_id)
        if html is None and render_html:
            html, rendered_pages = render_for_validation(cv, profile)
            pages = pages if pages is not None else rendered_pages
        ctx = RuleContext(cv=cv, profile=profile, html=html, pages=pages, pdf=pdf)
        return profile, engine.run(ctx)

    def run_and_save(
        self,
        resume_id: int,
        profile_id: int | None = None,
        *,
        html: str | None = None,
        pages: int | None = None,
        pdf: PdfInfo | None = None,
        render_html: bool = False,
    ) -> ValidationReportOut:
        profile, report = self.run(
            resume_id, profile_id, html=html, pages=pages, pdf=pdf, render_html=render_html
        )
        return self.save_report(resume_id, profile.id, report)

    def save_report(
        self, resume_id: int, profile_id: int | None, report: Report
    ) -> ValidationReportOut:
        """Persist the report and commit (API / CLI)."""
        with self._write():
            row = _persist(self.session, resume_id, profile_id, report)
        return self.get_report(row.id)

    def get_report(self, report_id: int) -> ValidationReportOut:
        row = self.session.get(ValidationReport, report_id)
        if row is None:
            raise NotFoundError(f"No existe el reporte de validación con id {report_id}")
        return ValidationReportOut.model_validate(row)


def run_and_save(
    session: Session,
    resume_id: int,
    profile_id: int | None = None,
    *,
    html: str | None = None,
    pages: int | None = None,
    pdf: PdfInfo | None = None,
    render_html: bool = False,
) -> ValidationReportOut:
    """Functional form of :meth:`ValidationService.run_and_save`."""
    return ValidationService(session).run_and_save(
        resume_id, profile_id, html=html, pages=pages, pdf=pdf, render_html=render_html
    )


def save_report(
    session: Session, *, resume_id: int, profile_id: int | None, report: Report
) -> ValidationReportOut:
    """Persist a computed report **without committing**: the caller owns the transaction.

    Stable entry point for the export (``ExportService`` calls it inside its own unit of work).
    """
    row = _persist(session, resume_id, profile_id, report)
    return ValidationReportOut.model_validate(row)
