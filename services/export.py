"""Export orchestration (spec §10): validate → snapshot → render → PDF → verify → files."""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from export.docx import to_docx_bytes
from export.json_export import to_json_bytes
from export.pdf import PdfEngineError, PdfResult, html_to_pdf
from export.verify import verify
from models import ExportJob
from models.enums import Destination, ExportFormat, ExportStatus, Severity
from render.context import build_context
from render.filters import file_stem
from render.renderer import render
from schemas import ExportProfileOut, ResumeOut, ValidationReportOut
from services.base import TransactionalService
from services.errors import NotFoundError
from services.profile import ProfileService
from services.resume import ResumeService
from services.validation import save_report
from validator.types import PdfInfo, Report, RuleContext

log = logging.getLogger(__name__)

EngineFn = Callable[[RuleContext], Report]
TEXT_EXTRACTABLE = "technical.text_extractable"
COVERAGE_OK = 0.95
PHOTO_VARIANT = "sinfoto"


def null_engine(ctx: RuleContext) -> Report:
    """Stand-in while ``validator.engine`` does not exist: no findings, score 100."""
    return Report(score=100)


def default_engine() -> EngineFn:
    """``validator.engine.run`` if available (lazy import), else :func:`null_engine`."""
    try:
        module = importlib.import_module("validator.engine")
    except ModuleNotFoundError as exc:
        if exc.name not in {"validator.engine", "validator"}:
            raise
        log.warning("validator.engine no existe todavía: se exporta sin validación")
        return null_engine
    run: EngineFn = module.run
    return run


def export_basename(cv: ResumeOut, profile: ExportProfileOut) -> str:
    """``{Nombre}_{Apellido}_CV_{ats|correo}`` without accents or spaces."""
    tag = "ats" if profile.destination is Destination.ATS else "correo"
    return "_".join(p for p in (file_stem(cv.basics.full_name), "CV", tag) if p)


def _has_error(report: Report, rule_id: str) -> bool:
    return any(f.rule_id == rule_id and f.severity is Severity.ERROR for f in report.findings)


@dataclass
class ExportOutcome:
    job: ExportJob
    report: Report | None
    pdf_info: PdfInfo | None = None
    files: list[Path] = field(default_factory=list)


class ExportService(TransactionalService):
    def __init__(
        self,
        session: Session,
        *,
        engine: EngineFn | None = None,
        exports_dir: Path | None = None,
    ) -> None:
        super().__init__(session)
        self.engine = engine or default_engine()
        self.exports_dir = exports_dir or get_settings().exports_dir

    # ------------------------------------------------------------------ jobs & files

    def get_job(self, job_id: int) -> ExportJob:
        job = self.session.get(ExportJob, job_id)
        if job is None:
            raise NotFoundError(f"No existe la exportación con id {job_id}")
        return job

    def job_dir(self, job: ExportJob) -> Path:
        return self.exports_dir / str(job.id)

    def list_files(self, job: ExportJob) -> list[Path]:
        folder = self.job_dir(job)
        return sorted(p for p in folder.iterdir() if p.is_file()) if folder.is_dir() else []

    def file_for(self, job_id: int, fmt: ExportFormat, variant: str | None = None) -> Path:
        job = self.get_job(job_id)
        suffix = f"_{PHOTO_VARIANT}.{fmt.value}" if variant == PHOTO_VARIANT else f".{fmt.value}"
        for path in self.list_files(job):
            is_variant = path.name.endswith(f"_{PHOTO_VARIANT}.{fmt.value}")
            if path.name.endswith(suffix) and (variant == PHOTO_VARIANT or not is_variant):
                return path
        raise NotFoundError(f"La exportación {job_id} no tiene archivo {fmt.value}")

    # ------------------------------------------------------------------ run

    def run(
        self,
        resume_id: int,
        profile_id: int,
        formats: Sequence[ExportFormat] = (ExportFormat.PDF,),
        with_photo_variant: bool = False,
    ) -> ExportOutcome:
        fmts = list(dict.fromkeys(formats)) or [ExportFormat.PDF]
        resumes = ResumeService(self.session)
        cv = resumes.get_out(resume_id)
        profile = ExportProfileOut.model_validate(
            ProfileService(self.session).get(profile_id, resume_id)
        )
        with self._write():
            job = ExportJob(
                resume_id=resume_id,
                profile_id=profile_id,
                format=fmts[0],
                status=ExportStatus.PENDING,
            )
            self.session.add(job)
            self.session.flush()
        try:
            return self._run(job, resumes, cv, profile, fmts, with_photo_variant)
        except Exception as exc:
            log.exception("Exportación %s falló", job.id)
            self.session.rollback()
            return self._finish(job, cv, profile, None, ExportStatus.FAILED, error=str(exc))

    def _run(
        self,
        job: ExportJob,
        resumes: ResumeService,
        cv: ResumeOut,
        profile: ExportProfileOut,
        fmts: list[ExportFormat],
        with_photo_variant: bool,
    ) -> ExportOutcome:
        destination = profile.destination
        html = render(cv, profile).html
        # 1. pre-render validation (no PDF yet): ats with errors → blocked, no files.
        pre = self.engine(RuleContext(cv=cv, profile=profile, html=html))
        if pre.blocks_export(destination):
            return self._finish(
                job, cv, profile, pre, ExportStatus.BLOCKED,
                error=f"Exportación bloqueada: {pre.errors} error(es) de validación",
            )  # fmt: skip
        # 2. immutable snapshot of what is exported.
        snapshot = resumes.create_snapshot(cv.id, f"Exportación #{job.id} · {profile.name}")
        # 3. HTML → PDF → round-trip → full validation (pre + technical.*).
        ctx = build_context(cv, profile)
        title, author = ctx["doc_title"], ctx["basics"]["full_name"]
        try:
            pdf = html_to_pdf(html, title=title, author=author)
        except PdfEngineError as exc:
            return self._finish(
                job, cv, profile, pre, ExportStatus.FAILED, error=str(exc), snapshot_id=snapshot.id
            )
        base = export_basename(cv, profile)
        info = verify(pdf.data, cv, filename=f"{base}.pdf", profile=profile)
        report = self.engine(
            RuleContext(cv=cv, profile=profile, html=html, pages=pdf.pages, pdf=info)
        )
        status, error = ExportStatus.DONE, None
        if destination is Destination.ATS and _has_error(report, TEXT_EXTRACTABLE):
            status = ExportStatus.FAILED
            error = f"El texto del PDF no es extraíble (cobertura {info.coverage:.0%})"
        elif report.blocks_export(destination):
            status = ExportStatus.BLOCKED
            error = f"Exportación bloqueada: {report.errors} error(es) de validación"
        files: list[Path] = []
        if status is ExportStatus.DONE:  # 4. files only for successful exports
            files = self._write_files(
                job, cv, profile, pdf, fmts, with_photo_variant, title, author
            )
        return self._finish(
            job, cv, profile, report, status,
            error=error, snapshot_id=snapshot.id, pdf=pdf, info=info, files=files,
        )  # fmt: skip

    def _write_files(
        self,
        job: ExportJob,
        cv: ResumeOut,
        profile: ExportProfileOut,
        pdf: PdfResult,
        fmts: list[ExportFormat],
        with_photo_variant: bool,
        title: str,
        author: str,
    ) -> list[Path]:
        folder = self.job_dir(job)
        folder.mkdir(parents=True, exist_ok=True)
        base = export_basename(cv, profile)
        outputs: list[tuple[str, bytes]] = []
        if ExportFormat.PDF in fmts:
            outputs.append((f"{base}.pdf", pdf.data))
            if (
                with_photo_variant
                and profile.destination is Destination.MAIL
                and profile.include_photo
            ):
                no_photo = profile.model_copy(update={"include_photo": False})
                variant = html_to_pdf(render(cv, no_photo).html, title=title, author=author)
                outputs.append((f"{base}_{PHOTO_VARIANT}.pdf", variant.data))
        if ExportFormat.DOCX in fmts:
            outputs.append((f"{base}.docx", to_docx_bytes(cv, profile)))
        if ExportFormat.JSON in fmts:
            outputs.append((f"{base}.json", to_json_bytes(cv)))
        paths = []
        for name, data in outputs:
            path = folder / name
            path.write_bytes(data)
            paths.append(path)
        return paths

    # ------------------------------------------------------------------ persistence

    def _persist_report(
        self, cv: ResumeOut, profile: ExportProfileOut, report: Report
    ) -> ValidationReportOut:
        """Persisted through the validator service (inside this unit of work, no commit)."""
        return save_report(self.session, resume_id=cv.id, profile_id=profile.id, report=report)

    def _finish(
        self,
        job: ExportJob,
        cv: ResumeOut,
        profile: ExportProfileOut,
        report: Report | None,
        status: ExportStatus,
        *,
        error: str | None = None,
        snapshot_id: int | None = None,
        pdf: PdfResult | None = None,
        info: PdfInfo | None = None,
        files: Iterable[Path] = (),
    ) -> ExportOutcome:
        written = list(files)
        with self._write():
            job = self.get_job(job.id)
            if report is not None:
                job.report_id = self._persist_report(cv, profile, report).id
            job.status = status
            job.error = error
            job.snapshot_id = snapshot_id
            job.pages = pdf.pages if pdf else None
            job.roundtrip_ok = (info.has_text and info.coverage >= COVERAGE_OK) if info else None
            job.output_path = str(self.job_dir(job)) if written else None
            self.session.flush()
        return ExportOutcome(job=job, report=report, pdf_info=info, files=written)
