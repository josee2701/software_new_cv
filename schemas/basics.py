from __future__ import annotations

from typing import Annotated

from pydantic import EmailStr, Field, model_validator

from models.enums import LinkKind
from schemas.common import (
    CountryCode,
    InputModel,
    OptStr80,
    OptStr1200,
    OutModel,
    UrlStr,
    normalize_phone,
)
from schemas.errors import FieldValueError

Str80 = Annotated[str, Field(min_length=1, max_length=80)]


class AssetOut(OutModel):
    id: int
    filename: str
    original_name: str
    mime: str
    width: int
    height: int
    size_bytes: int
    sha256: str


class BasicsCreate(InputModel):
    full_name: Annotated[str, Field(min_length=1, max_length=120)]
    headline: Annotated[str, Field(min_length=1, max_length=160)]
    email: EmailStr
    phone: Annotated[str, Field(min_length=1, max_length=30)]
    city: Str80
    region: OptStr80 = None
    country: CountryCode = "CO"
    summary: OptStr1200 = None
    photo_asset_id: int | None = None

    @model_validator(mode="after")
    def _normalize_phone(self) -> BasicsCreate:
        try:
            self.phone = normalize_phone(self.phone, self.country)
        except ValueError as exc:
            raise FieldValueError("phone", str(exc)) from exc
        return self


class BasicsUpdate(InputModel):
    """Partial update (``PUT /basics`` merges only the fields sent)."""

    full_name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    headline: Annotated[str, Field(min_length=1, max_length=160)] | None = None
    email: EmailStr | None = None
    phone: Annotated[str, Field(min_length=1, max_length=30)] | None = None
    city: Str80 | None = None
    region: OptStr80 = None
    country: CountryCode | None = None
    summary: OptStr1200 = None
    photo_asset_id: int | None = None

    @model_validator(mode="after")
    def _normalize_phone(self) -> BasicsUpdate:
        if self.phone is not None:
            try:
                self.phone = normalize_phone(self.phone, self.country or "CO")
            except ValueError as exc:
                raise FieldValueError("phone", str(exc)) from exc
        return self


class BasicsOut(OutModel):
    id: int
    full_name: str
    headline: str
    email: str  # plain str: a freshly created resume has empty basics
    phone: str
    city: str
    region: str | None
    country: str
    summary: str | None
    photo_asset_id: int | None
    photo: AssetOut | None = None


class ContactLinkCreate(InputModel):
    kind: LinkKind
    label: OptStr80 = None
    url: UrlStr


class ContactLinkUpdate(InputModel):
    kind: LinkKind | None = None
    label: OptStr80 = None
    url: UrlStr | None = None


class ContactLinkOut(OutModel):
    id: int
    kind: LinkKind
    label: str | None
    url: str
    position: int
