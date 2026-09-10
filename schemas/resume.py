from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field

from schemas.basics import BasicsOut, ContactLinkOut
from schemas.certification import CertificationOut
from schemas.common import InputModel, OptStr, OptStr80, OutModel
from schemas.education import EducationOut
from schemas.experience import ExperienceOut
from schemas.language import LanguageOut
from schemas.profile import ExportProfileOut
from schemas.project import ProjectOut
from schemas.skill import SkillCategoryOut

Lang = Literal["es", "en"]


class ResumeCreate(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    language: Lang = "es"
    is_default: bool = False
    notes: OptStr = None


class ResumeUpdate(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    language: Lang | None = None
    is_default: bool | None = None
    notes: OptStr = None


class ResumeDuplicate(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None


class ResumeSummaryOut(OutModel):
    id: int
    name: str
    language: Lang
    is_default: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ResumeOut(ResumeSummaryOut):
    """Full nested tree: the contract consumed by render, validator, snapshot and export."""

    basics: BasicsOut
    links: list[ContactLinkOut] = Field(default_factory=list)
    experiences: list[ExperienceOut] = Field(default_factory=list)
    education: list[EducationOut] = Field(default_factory=list)
    skill_categories: list[SkillCategoryOut] = Field(default_factory=list)
    projects: list[ProjectOut] = Field(default_factory=list)
    certifications: list[CertificationOut] = Field(default_factory=list)
    languages: list[LanguageOut] = Field(default_factory=list)
    profiles: list[ExportProfileOut] = Field(default_factory=list)


class SnapshotCreate(InputModel):
    label: OptStr80 = None


class SnapshotOut(OutModel):
    id: int
    resume_id: int
    label: str | None
    created_at: datetime


class SnapshotDetailOut(SnapshotOut):
    payload: dict[str, Any]
