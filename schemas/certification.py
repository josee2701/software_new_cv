from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import Field, model_validator

from models.enums import ShowIn
from schemas.common import InputModel, MonthDate, OptStr, OptStr80, OptUrlStr, OutModel
from schemas.errors import FieldValueError


class CertificationCreate(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=160)]
    issuer: Annotated[str, Field(min_length=1, max_length=120)]
    issue_date: MonthDate | None = None
    expiry_date: MonthDate | None = None
    credential_id: OptStr80 = None
    url: OptUrlStr = None
    show_in: ShowIn = ShowIn.BOTH

    @model_validator(mode="after")
    def _check_dates(self) -> CertificationCreate:
        if self.issue_date and self.expiry_date and self.expiry_date < self.issue_date:
            raise FieldValueError(
                "expiry_date", "La fecha de vencimiento no puede ser anterior a la de expedición"
            )
        return self


class CertificationUpdate(InputModel):
    name: str | None = None
    issuer: str | None = None
    issue_date: MonthDate | None = None
    expiry_date: MonthDate | None = None
    credential_id: OptStr = None
    url: OptUrlStr = None
    show_in: ShowIn | None = None


class CertificationOut(OutModel):
    id: int
    name: str
    issuer: str
    issue_date: date | None
    expiry_date: date | None
    credential_id: str | None
    url: str | None
    show_in: ShowIn
    position: int
