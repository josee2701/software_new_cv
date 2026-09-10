"""Shared Pydantic types and validators (spec §5)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
)

# ---------------------------------------------------------------------------- base models


class InputModel(BaseModel):
    """Base for Create/Update schemas: strips strings and rejects unknown fields."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class OutModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------- dates

_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?$")


def parse_month_date(value: Any) -> Any:
    """Accept ``YYYY-MM`` / ``YYYY-MM-DD`` (or ``date``) and store it as day 01."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().replace(day=1)
    if isinstance(value, date):
        return value.replace(day=1)
    if isinstance(value, str):
        raw = value.strip()
        if raw == "":
            return None
        match = _DATE_RE.match(raw)
        if not match:
            raise ValueError("Fecha inválida: usa el formato AAAA-MM o AAAA-MM-DD")
        year, month = int(match.group(1)), int(match.group(2))
        day = int(match.group(3)) if match.group(3) else 1
        try:
            date(year, month, day)
        except ValueError as exc:
            raise ValueError("Fecha inválida: el mes o el día no existen") from exc
        return date(year, month, 1)
    return value


MonthDate = Annotated[date, BeforeValidator(parse_month_date)]


# ---------------------------------------------------------------------------- text helpers


def collapse_spaces(value: str) -> str:
    return " ".join(value.split())


def empty_to_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


OptStr = Annotated[str | None, BeforeValidator(empty_to_none)]
# Optional strings with a max length: the constraint must sit inside the union so it is never
# applied to ``None``.
OptStr10 = Annotated[Annotated[str, Field(max_length=10)] | None, BeforeValidator(empty_to_none)]
OptStr30 = Annotated[Annotated[str, Field(max_length=30)] | None, BeforeValidator(empty_to_none)]
OptStr40 = Annotated[Annotated[str, Field(max_length=40)] | None, BeforeValidator(empty_to_none)]
OptStr60 = Annotated[Annotated[str, Field(max_length=60)] | None, BeforeValidator(empty_to_none)]
OptStr80 = Annotated[Annotated[str, Field(max_length=80)] | None, BeforeValidator(empty_to_none)]
OptStr120 = Annotated[Annotated[str, Field(max_length=120)] | None, BeforeValidator(empty_to_none)]
OptStr400 = Annotated[Annotated[str, Field(max_length=400)] | None, BeforeValidator(empty_to_none)]
OptStr1200 = Annotated[
    Annotated[str, Field(max_length=1200)] | None, BeforeValidator(empty_to_none)
]

_BULLET_RE = re.compile(r"^[\s•\-*–·]+")


def clean_bullet(value: Any) -> Any:
    """Strip, remove a leading bullet ("•", "-", "*", "–", "·") and collapse spaces."""
    if not isinstance(value, str):
        return value
    return collapse_spaces(_BULLET_RE.sub("", value.strip()))


# ---------------------------------------------------------------------------- phone (E.164)

CALLING_CODES: dict[str, str] = {
    "CO": "57",
    "MX": "52",
    "AR": "54",
    "CL": "56",
    "PE": "51",
    "EC": "593",
    "VE": "58",
    "BO": "591",
    "PY": "595",
    "UY": "598",
    "BR": "55",
    "PA": "507",
    "CR": "506",
    "GT": "502",
    "SV": "503",
    "HN": "504",
    "NI": "505",
    "DO": "1",
    "PR": "1",
    "CU": "53",
    "US": "1",
    "CA": "1",
    "ES": "34",
    "GB": "44",
    "DE": "49",
    "FR": "33",
    "IT": "39",
    "PT": "351",
}
_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
PHONE_ERROR = "Teléfono inválido: usa formato internacional, p. ej. +57 300 123 4567"


def normalize_phone(raw: str, default_country: str = "CO") -> str:
    """Normalize to E.164 (``+573001234567``). Numbers without prefix use the country code."""
    value = raw.strip()
    if not value:
        raise ValueError(PHONE_ERROR)
    if re.search(r"[^\d\s()+.\-/]", value):
        raise ValueError(PHONE_ERROR)
    has_plus = value.startswith("+")
    digits = re.sub(r"\D", "", value)
    if has_plus:
        candidate = "+" + digits
    elif digits.startswith("00"):
        candidate = "+" + digits[2:]
    else:
        code = CALLING_CODES.get(default_country.upper(), "57")
        national = digits.lstrip("0") if code != "39" else digits
        # A number already carrying the country code (e.g. "573001234567").
        if national.startswith(code) and len(national) > 10:
            candidate = "+" + national
        else:
            candidate = "+" + code + national
    if not _E164_RE.match(candidate):
        raise ValueError(PHONE_ERROR)
    return candidate


# ---------------------------------------------------------------------------- country / urls


def _upper_country(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", value):
            raise ValueError("País inválido: usa el código ISO de 2 letras (p. ej. CO)")
    return value


def _opt_upper_country(value: Any) -> Any:
    return _upper_country(empty_to_none(value))


CountryCode = Annotated[str, BeforeValidator(_upper_country)]
OptCountryCode = Annotated[str | None, BeforeValidator(_opt_upper_country)]

_URL_ADAPTER: TypeAdapter[HttpUrl] = TypeAdapter(HttpUrl)


def _check_url(value: str) -> str:
    value = value.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", value):
        value = "https://" + value
    try:
        _URL_ADAPTER.validate_python(value)
    except ValueError as exc:
        raise ValueError("URL inválida") from exc
    if len(value) > 500:
        raise ValueError("Máximo 500 caracteres")
    return value


def _check_opt_url(value: str | None) -> str | None:
    return None if value is None else _check_url(value)


UrlStr = Annotated[str, AfterValidator(_check_url)]
OptUrlStr = Annotated[str | None, BeforeValidator(empty_to_none), AfterValidator(_check_opt_url)]
