from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import Field, model_validator

from models.enums import DegreeLevel, ShowIn
from schemas.common import (
    InputModel,
    MonthDate,
    OptStr,
    OptStr10,
    OptStr80,
    OptStr120,
    OptStr400,
    OutModel,
)
from schemas.errors import FieldValueError


class EducationCreate(InputModel):
    institution: Annotated[str, Field(min_length=1, max_length=160)]
    degree: Annotated[str, Field(min_length=1, max_length=160)]
    level: DegreeLevel | None = None
    field: OptStr120 = None
    city: OptStr80 = None
    start_date: MonthDate | None = None
    end_date: MonthDate | None = None
    in_progress: bool = False
    gpa: OptStr10 = None
    description: OptStr400 = None
    show_in: ShowIn = ShowIn.BOTH

    @model_validator(mode="after")
    def _check_dates(self) -> EducationCreate:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise FieldValueError(
                "end_date", "La fecha de fin no puede ser anterior a la de inicio"
            )
        return self


class EducationUpdate(InputModel):
    institution: str | None = None
    degree: str | None = None
    level: DegreeLevel | None = None
    field: OptStr = None
    city: OptStr = None
    start_date: MonthDate | None = None
    end_date: MonthDate | None = None
    in_progress: bool | None = None
    gpa: OptStr = None
    description: OptStr = None
    show_in: ShowIn | None = None


class EducationOut(OutModel):
    id: int
    institution: str
    degree: str
    level: DegreeLevel | None
    field: str | None
    city: str | None
    start_date: date | None
    end_date: date | None
    in_progress: bool
    gpa: str | None
    description: str | None
    show_in: ShowIn
    position: int
