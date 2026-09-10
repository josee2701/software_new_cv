from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from models.enums import Density, Destination, SectionKey
from schemas.common import InputModel, OptStr, OptStr60, OutModel
from schemas.errors import FieldValueError

THEMES = ("slate", "ocean", "graphite")
ATS_FONTS = ("Arial", "Calibri", "Helvetica", "Georgia")
DateFormat = Literal["MM/YYYY", "MMM YYYY", "YYYY"]
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _check_color(value: str | None) -> str | None:
    if value is not None and not _HEX_RE.match(value):
        raise ValueError("Color inválido: usa el formato #RRGGBB")
    return value


class ExportProfileCreate(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=60)]
    destination: Destination
    theme: OptStr = None
    accent_color: OptStr = None
    density: Density = Density.NORMAL
    include_photo: bool = False
    max_pages: Literal[1, 2, 3] = 2
    date_format: DateFormat = "MM/YYYY"
    font_family: Annotated[str, Field(min_length=1, max_length=40)] = "Arial"

    _color = field_validator("accent_color")(_check_color)

    @model_validator(mode="after")
    def _destination_rules(self) -> ExportProfileCreate:
        if self.destination == Destination.ATS:
            if self.include_photo:
                raise FieldValueError("include_photo", "El destino Plataforma (ATS) no admite foto")
            if self.theme is not None:
                raise FieldValueError("theme", "El destino Plataforma (ATS) no usa tema")
            if self.accent_color is not None:
                raise FieldValueError(
                    "accent_color", "El destino Plataforma (ATS) no usa color de acento"
                )
            if self.font_family not in ATS_FONTS:
                raise FieldValueError(
                    "font_family", "Fuente no permitida para ATS; usa: " + ", ".join(ATS_FONTS)
                )
        else:
            if self.theme is None:
                raise FieldValueError("theme", "El destino Correo requiere un tema")
            if self.theme not in THEMES:
                raise FieldValueError("theme", "Tema inválido; opciones: " + ", ".join(THEMES))
        return self


class ExportProfileUpdate(InputModel):
    name: str | None = None
    destination: Destination | None = None
    theme: OptStr = None
    accent_color: OptStr = None
    density: Density | None = None
    include_photo: bool | None = None
    max_pages: Literal[1, 2, 3] | None = None
    date_format: DateFormat | None = None
    font_family: str | None = None


class ProfileSectionIn(InputModel):
    section: SectionKey
    visible: bool = True
    title_override: OptStr60 = None


class ProfileSectionOut(OutModel):
    id: int
    section: SectionKey
    visible: bool
    position: int
    title_override: str | None


class ExportProfileOut(OutModel):
    id: int
    resume_id: int
    name: str
    destination: Destination
    theme: str | None
    accent_color: str | None
    density: Density
    include_photo: bool
    max_pages: int
    date_format: str
    font_family: str
    sections: list[ProfileSectionOut] = Field(default_factory=list)
