"""Export request / result schemas (spec §6, §10)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from models.enums import ExportFormat, ExportStatus, Severity
from schemas.common import InputModel, OutModel


class ExportRequest(InputModel):
    profile_id: int
    formats: Annotated[list[ExportFormat], Field(min_length=1, max_length=3)] = Field(
        default_factory=lambda: [ExportFormat.PDF]
    )
    with_photo_variant: bool = False


class ExportFindingOut(BaseModel):
    rule_id: str
    severity: Severity
    message: str
    section: str | None = None
    entity: str | None = None
    entity_id: int | None = None
    suggestion: str | None = None


class ExportJobOut(OutModel):
    id: int
    resume_id: int
    profile_id: int
    format: ExportFormat
    status: ExportStatus
    output_path: str | None
    report_id: int | None
    snapshot_id: int | None
    error: str | None
    pages: int | None
    roundtrip_ok: bool | None
    created_at: datetime


class ExportResultOut(BaseModel):
    job: ExportJobOut
    files: list[str] = Field(default_factory=list)
    downloads: list[str] = Field(default_factory=list)  # API paths to download each file
    score: int | None = None
    errors: int = 0
    warnings: int = 0
    coverage: float | None = None
    findings: list[ExportFindingOut] = Field(default_factory=list)
