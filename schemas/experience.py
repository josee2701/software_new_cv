from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BeforeValidator, Field, model_validator

from models.enums import ShowIn
from schemas.common import (
    InputModel,
    MonthDate,
    OptCountryCode,
    OptStr,
    OptStr30,
    OptStr40,
    OptStr80,
    OptStr400,
    OutModel,
    clean_bullet,
)
from schemas.errors import FieldValueError

CleanAchievement = Annotated[
    str, BeforeValidator(clean_bullet), Field(min_length=1, max_length=300)
]


class ExperienceCreate(InputModel):
    company: Annotated[str, Field(min_length=1, max_length=120)]
    role: Annotated[str, Field(min_length=1, max_length=120)]
    employment_type: OptStr30 = None
    city: OptStr80 = None
    country: OptCountryCode = None
    remote: bool = False
    start_date: MonthDate
    end_date: MonthDate | None = None
    is_current: bool = False
    description: OptStr400 = None
    show_in: ShowIn = ShowIn.BOTH

    @model_validator(mode="after")
    def _check_dates(self) -> ExperienceCreate:
        if self.is_current and self.end_date is not None:
            raise FieldValueError("end_date", "Si es tu trabajo actual no debe tener fecha de fin")
        if not self.is_current and self.end_date is None:
            raise FieldValueError(
                "end_date", "Indica la fecha de fin o marca la experiencia como actual"
            )
        if self.end_date is not None and self.end_date < self.start_date:
            raise FieldValueError(
                "end_date", "La fecha de fin no puede ser anterior a la de inicio"
            )
        return self


class ExperienceUpdate(InputModel):
    company: str | None = None
    role: str | None = None
    employment_type: OptStr = None
    city: OptStr = None
    country: OptCountryCode = None
    remote: bool | None = None
    start_date: MonthDate | None = None
    end_date: MonthDate | None = None
    is_current: bool | None = None
    description: OptStr = None
    show_in: ShowIn | None = None


class AchievementCreate(InputModel):
    text: CleanAchievement
    metric_value: OptStr40 = None
    show_in: ShowIn = ShowIn.BOTH


class AchievementUpdate(InputModel):
    text: Annotated[str, BeforeValidator(clean_bullet)] | None = None
    metric_value: OptStr = None
    show_in: ShowIn | None = None


class AchievementOut(OutModel):
    id: int
    text: str
    metric_value: str | None
    show_in: ShowIn
    position: int


class ExperienceOut(OutModel):
    id: int
    company: str
    role: str
    employment_type: str | None
    city: str | None
    country: str | None
    remote: bool
    start_date: date
    end_date: date | None
    is_current: bool
    description: str | None
    show_in: ShowIn
    position: int
    achievements: list[AchievementOut] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
