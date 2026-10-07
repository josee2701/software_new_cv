"""Import preview (spec §11): every parsed field carries a ``confidence`` in 0..1.

The preview never writes to the database; the user edits it and then applies it.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from models.enums import DegreeLevel, LanguageLevel, LinkKind
from schemas.resume import ResumeOut

Confidence = Annotated[float, Field(ge=0, le=1)]


class _Scored(BaseModel):
    confidence: Confidence = 0.0


class ScoredStr(_Scored):
    value: str = ""


class ScoredOptStr(_Scored):
    value: str | None = None


class ScoredDate(_Scored):
    value: date | None = None


class ScoredBool(_Scored):
    value: bool = False


class ScoredList(_Scored):
    value: list[str] = Field(default_factory=list)


class ScoredDegree(_Scored):
    value: DegreeLevel | None = None


class ScoredLanguageLevel(_Scored):
    value: LanguageLevel = LanguageLevel.B1


class ImportedBasics(BaseModel):
    full_name: ScoredStr = Field(default_factory=ScoredStr)
    headline: ScoredStr = Field(default_factory=ScoredStr)
    email: ScoredStr = Field(default_factory=ScoredStr)
    phone: ScoredStr = Field(default_factory=ScoredStr)
    city: ScoredStr = Field(default_factory=ScoredStr)
    region: ScoredOptStr = Field(default_factory=ScoredOptStr)
    country: ScoredOptStr = Field(default_factory=ScoredOptStr)
    summary: ScoredOptStr = Field(default_factory=ScoredOptStr)


class ImportedLink(BaseModel):
    kind: LinkKind
    url: str
    confidence: Confidence = 0.0


class ImportedText(BaseModel):
    text: str
    confidence: Confidence = 0.0


class ImportedExperience(BaseModel):
    role: ScoredStr = Field(default_factory=ScoredStr)
    company: ScoredStr = Field(default_factory=ScoredStr)
    city: ScoredOptStr = Field(default_factory=ScoredOptStr)
    country: ScoredOptStr = Field(default_factory=ScoredOptStr)
    remote: ScoredBool = Field(default_factory=ScoredBool)
    start_date: ScoredDate = Field(default_factory=ScoredDate)
    end_date: ScoredDate = Field(default_factory=ScoredDate)
    is_current: ScoredBool = Field(default_factory=ScoredBool)
    description: ScoredOptStr = Field(default_factory=ScoredOptStr)
    achievements: list[ImportedText] = Field(default_factory=list)
    technologies: ScoredList = Field(default_factory=ScoredList)


class ImportedEducation(BaseModel):
    degree: ScoredStr = Field(default_factory=ScoredStr)
    institution: ScoredStr = Field(default_factory=ScoredStr)
    level: ScoredDegree = Field(default_factory=ScoredDegree)
    field: ScoredOptStr = Field(default_factory=ScoredOptStr)
    city: ScoredOptStr = Field(default_factory=ScoredOptStr)
    start_date: ScoredDate = Field(default_factory=ScoredDate)
    end_date: ScoredDate = Field(default_factory=ScoredDate)
    in_progress: ScoredBool = Field(default_factory=ScoredBool)
    gpa: ScoredOptStr = Field(default_factory=ScoredOptStr)


class ImportedSkillCategory(BaseModel):
    name: ScoredStr = Field(default_factory=ScoredStr)
    skills: list[ImportedText] = Field(default_factory=list)


class ImportedProject(BaseModel):
    name: ScoredStr = Field(default_factory=ScoredStr)
    role: ScoredOptStr = Field(default_factory=ScoredOptStr)
    description: ScoredStr = Field(default_factory=ScoredStr)
    url: ScoredOptStr = Field(default_factory=ScoredOptStr)
    start_date: ScoredDate = Field(default_factory=ScoredDate)
    end_date: ScoredDate = Field(default_factory=ScoredDate)
    technologies: ScoredList = Field(default_factory=ScoredList)


class ImportedCertification(BaseModel):
    name: ScoredStr = Field(default_factory=ScoredStr)
    issuer: ScoredStr = Field(default_factory=ScoredStr)
    issue_date: ScoredDate = Field(default_factory=ScoredDate)
    expiry_date: ScoredDate = Field(default_factory=ScoredDate)
    credential_id: ScoredOptStr = Field(default_factory=ScoredOptStr)
    url: ScoredOptStr = Field(default_factory=ScoredOptStr)


class ImportedLanguage(BaseModel):
    name: ScoredStr = Field(default_factory=ScoredStr)
    level: ScoredLanguageLevel = Field(default_factory=ScoredLanguageLevel)


class SectionInfo(BaseModel):
    kind: str  # summary | experience | … | header | contact | other
    title: str
    confidence: Confidence
    lines: int


class ImportPreview(BaseModel):
    source: Literal["pdf", "docx"]
    filename: str | None = None
    basics: ImportedBasics = Field(default_factory=ImportedBasics)
    links: list[ImportedLink] = Field(default_factory=list)
    experiences: list[ImportedExperience] = Field(default_factory=list)
    education: list[ImportedEducation] = Field(default_factory=list)
    skill_categories: list[ImportedSkillCategory] = Field(default_factory=list)
    projects: list[ImportedProject] = Field(default_factory=list)
    certifications: list[ImportedCertification] = Field(default_factory=list)
    languages: list[ImportedLanguage] = Field(default_factory=list)
    sections: list[SectionInfo] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unassigned: list[str] = Field(default_factory=list)  # lines not understood (for the UI)


class ImportApplyRequest(BaseModel):
    preview: ImportPreview
    mode: Literal["replace", "append"] = "replace"


class SkippedItem(BaseModel):
    path: str  # e.g. "experiences.2"
    reason: str


class ImportApplyResult(BaseModel):
    resume: ResumeOut
    created: dict[str, int] = Field(default_factory=dict)
    skipped: list[SkippedItem] = Field(default_factory=list)
