"""Exports: run (``POST /resumes/{id}/export``), job detail and file download."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse

from app.deps import SessionDep
from models.enums import ExportFormat
from schemas.export import ExportFindingOut, ExportJobOut, ExportRequest, ExportResultOut
from services.export import PHOTO_VARIANT, EngineFn, ExportOutcome, ExportService, default_engine

router = APIRouter(tags=["exports"])

MEDIA_TYPES = {
    ExportFormat.PDF: "application/pdf",
    ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ExportFormat.JSON: "application/json",
}


def get_validation_engine() -> EngineFn:
    """Validation engine used by exports (overridable in tests)."""
    return default_engine()


EngineDep = Annotated[EngineFn, Depends(get_validation_engine)]


def _download_path(job_id: int, name: str) -> str:
    fmt = name.rsplit(".", 1)[-1]
    variant = f"&variant={PHOTO_VARIANT}" if name.endswith(f"_{PHOTO_VARIANT}.{fmt}") else ""
    return f"/api/exports/{job_id}/download?format={fmt}{variant}"


def _result(outcome: ExportOutcome, files: list[str]) -> ExportResultOut:
    report, info = outcome.report, outcome.pdf_info
    return ExportResultOut(
        job=ExportJobOut.model_validate(outcome.job),
        files=files,
        downloads=[_download_path(outcome.job.id, name) for name in files],
        score=report.score if report else None,
        errors=report.errors if report else 0,
        warnings=report.warnings if report else 0,
        coverage=info.coverage if info else None,
        findings=[
            ExportFindingOut(
                rule_id=f.rule_id,
                severity=f.severity,
                message=f.message,
                section=f.section,
                entity=f.entity,
                entity_id=f.entity_id,
                suggestion=f.suggestion,
            )
            for f in (report.findings if report else ())
        ],
    )


@router.post(
    "/resumes/{resume_id}/export",
    response_model=ExportResultOut,
    status_code=status.HTTP_201_CREATED,
)
def export_resume(
    resume_id: int, body: ExportRequest, session: SessionDep, engine: EngineDep
) -> ExportResultOut:
    """Validate and export. ``job.status``: done | blocked (ats with errors) | failed."""
    outcome = ExportService(session, engine=engine).run(
        resume_id, body.profile_id, body.formats, body.with_photo_variant
    )
    return _result(outcome, [p.name for p in outcome.files])


@router.get("/exports/{job_id}", response_model=ExportJobOut)
def get_export(job_id: int, session: SessionDep) -> ExportJobOut:
    return ExportJobOut.model_validate(ExportService(session, engine=None).get_job(job_id))


@router.get("/exports/{job_id}/download", response_class=FileResponse)
def download_export(
    job_id: int,
    session: SessionDep,
    fmt: Annotated[ExportFormat, Query(alias="format")] = ExportFormat.PDF,
    variant: Annotated[Literal["sinfoto"] | None, Query()] = None,
) -> FileResponse:
    path = ExportService(session, engine=None).file_for(job_id, fmt, variant)
    return FileResponse(path, media_type=MEDIA_TYPES[fmt], filename=path.name)
