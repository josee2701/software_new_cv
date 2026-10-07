"""Import a PDF/DOCX: preview (no writes) and apply (spec §6, §11)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.deps import SessionDep
from schemas.importer import ImportApplyRequest, ImportApplyResult, ImportPreview
from services.importer import MAX_UPLOAD_BYTES, ImportService

router = APIRouter(tags=["import"])


@router.post("/resumes/{resume_id}/import", response_model=ImportPreview)
async def import_file(
    resume_id: int, file: Annotated[UploadFile, File()], session: SessionDep
) -> ImportPreview:
    """Multipart PDF/DOCX → ``ImportPreview`` with a confidence per field. Writes nothing."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    return ImportService(session).preview(resume_id, data, file.filename)


@router.post("/resumes/{resume_id}/import/apply", response_model=ImportApplyResult)
def apply_import(
    resume_id: int, body: ImportApplyRequest, session: SessionDep
) -> ImportApplyResult:
    """Apply the edited preview (``mode``: replace | append) in one transaction."""
    return ImportService(session).apply(resume_id, body.preview, body.mode)
