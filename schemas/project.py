from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import Field, model_validator

from models.enums import ShowIn
from schemas.common import InputModel, MonthDate, OptStr, OptStr120, OptUrlStr, OutModel
from schemas.errors import FieldValueError


class ProjectCreate(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    role: OptStr120 = None
    description: Annotated[str, Field(min_length=1, max_length=600)]
    url: OptUrlStr = None
    start_date: MonthDate | None = None
    end_date: MonthDate | None = None
    show_in: ShowIn = ShowIn.BOTH

    @model_validator(mode="after")
    def _check_dates(self) -> ProjectCreate:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise FieldValueError(
                "end_date", "La fecha de fin no puede ser anterior a la de inicio"
            )
        return self


class ProjectUpdate(InputModel):
    name: str | None = None
    role: OptStr = None
    description: str | None = None
    url: OptUrlStr = None
    start_date: MonthDate | None = None
    end_date: MonthDate | None = None
    show_in: ShowIn | None = None


class ProjectOut(OutModel):
    id: int
    name: str
    role: str | None
    description: str
    url: str | None
    start_date: date | None
    end_date: date | None
    show_in: ShowIn
    position: int
    technologies: list[str] = Field(default_factory=list)
