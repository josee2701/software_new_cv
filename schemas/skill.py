from __future__ import annotations

from typing import Annotated

from pydantic import Field

from models.enums import ShowIn, SkillLevel
from schemas.common import InputModel, OutModel

Name60 = Annotated[str, Field(min_length=1, max_length=60)]


class SkillCategoryCreate(InputModel):
    name: Name60


class SkillCategoryUpdate(InputModel):
    name: str | None = None


class SkillCreate(InputModel):
    name: Name60
    level: SkillLevel | None = None
    years: Annotated[int, Field(ge=0, le=50)] | None = None
    technology_id: int | None = None
    show_in: ShowIn = ShowIn.BOTH


class SkillUpdate(InputModel):
    name: str | None = None
    level: SkillLevel | None = None
    years: int | None = None
    technology_id: int | None = None
    show_in: ShowIn | None = None


class SkillOut(OutModel):
    id: int
    name: str
    level: SkillLevel | None
    years: int | None
    technology_id: int | None
    show_in: ShowIn
    position: int


class SkillCategoryOut(OutModel):
    id: int
    name: str
    position: int
    skills: list[SkillOut] = Field(default_factory=list)
