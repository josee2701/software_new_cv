from __future__ import annotations

from typing import Annotated

from pydantic import Field

from models.enums import LanguageLevel
from schemas.common import InputModel, OutModel


class LanguageCreate(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=40)]
    level: LanguageLevel


class LanguageUpdate(InputModel):
    name: str | None = None
    level: LanguageLevel | None = None


class LanguageOut(OutModel):
    id: int
    name: str
    level: LanguageLevel
    position: int
