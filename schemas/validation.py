"""Validation report schemas (``POST /api/resumes/{id}/validate``, spec §4.4 and §6)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from models.enums import Severity
from schemas.common import OutModel


class FindingOut(OutModel):
    id: int
    rule_id: str
    severity: Severity
    message: str
    section: str | None
    entity: str | None
    entity_id: int | None
    suggestion: str | None


class ValidationReportOut(OutModel):
    id: int
    resume_id: int
    profile_id: int | None
    score: int
    errors: int
    warnings: int
    created_at: datetime
    findings: list[FindingOut] = Field(default_factory=list)
