"""``POST /api/resumes/{id}/validate?profile_id=`` → ``ValidationReportOut`` (persisted)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import SessionDep
from schemas.validation import ValidationReportOut
from services.validation import ValidationService

router = APIRouter(tags=["validation"])


@router.post("/resumes/{resume_id}/validate", response_model=ValidationReportOut)
def validate_resume(
    resume_id: int,
    session: SessionDep,
    profile_id: Annotated[int | None, Query()] = None,
) -> ValidationReportOut:
    """Validate against the profile (first profile if omitted) using the rendered HTML."""
    return ValidationService(session).run_and_save(resume_id, profile_id, render_html=True)
