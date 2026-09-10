"""Conversion of Pydantic errors to the API error shape ``[{"field", "msg"}]`` (spec §6)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, TypedDict


class FieldError(TypedDict):
    field: str
    msg: str


class FieldValueError(ValueError):
    """``ValueError`` raised from a ``model_validator`` that names the offending field."""

    def __init__(self, field: str, msg: str) -> None:
        super().__init__(msg)
        self.field = field
        self.msg = msg


_SKIP_LOC = {"body", "query", "path", "header", "cookie"}

# Spanish messages for the most common built-in Pydantic error types.
_MESSAGES: dict[str, str] = {
    "missing": "Campo obligatorio",
    "string_type": "Debe ser texto",
    "int_type": "Debe ser un número entero",
    "int_parsing": "Debe ser un número entero",
    "bool_type": "Debe ser verdadero o falso",
    "bool_parsing": "Debe ser verdadero o falso",
    "date_type": "Fecha inválida",
    "date_parsing": "Fecha inválida",
    "date_from_datetime_parsing": "Fecha inválida",
    "list_type": "Debe ser una lista",
    "dict_type": "Debe ser un objeto",
    "model_attributes_type": "Debe ser un objeto",
    "extra_forbidden": "Campo no permitido",
    "json_invalid": "JSON inválido",
    "url_parsing": "URL inválida",
    "url_scheme": "La URL debe empezar por http:// o https://",
}


def _message(err: dict[str, Any]) -> str:
    kind = str(err.get("type", ""))
    ctx = err.get("ctx") or {}
    if kind == "value_error":
        msg = str(err.get("msg", "")).removeprefix("Value error, ")
        if msg.startswith("value is not a valid email address"):
            return "Correo electrónico inválido"
        return msg
    if kind == "string_too_short":
        n = ctx.get("min_length", 1)
        return "Campo obligatorio" if n == 1 else f"Mínimo {n} caracteres"
    if kind == "string_too_long":
        return f"Máximo {ctx.get('max_length')} caracteres"
    if kind == "string_pattern_mismatch":
        return "Formato inválido"
    if kind in {"greater_than_equal", "greater_than"}:
        return f"Debe ser mayor o igual a {ctx.get('ge', ctx.get('gt'))}"
    if kind in {"less_than_equal", "less_than"}:
        return f"Debe ser menor o igual a {ctx.get('le', ctx.get('lt'))}"
    if kind in {"enum", "literal_error"}:
        return f"Valor inválido; opciones: {ctx.get('expected', '')}".strip()
    if kind == "too_long":
        return f"Máximo {ctx.get('max_length')} elementos"
    return _MESSAGES.get(kind, str(err.get("msg", "Valor inválido")))


def _field(loc: Sequence[Any]) -> str:
    parts = [str(p) for p in loc]
    if parts and parts[0] in _SKIP_LOC:
        parts = parts[1:]
    return ".".join(parts)


def _one(err: dict[str, Any]) -> FieldError:
    loc = list(err.get("loc", ()))
    original = (err.get("ctx") or {}).get("error")
    if isinstance(original, FieldValueError):
        return FieldError(field=_field([*loc, original.field]), msg=original.msg)
    return FieldError(field=_field(loc), msg=_message(err))


def to_field_errors(errors: Iterable[Any]) -> list[FieldError]:
    """Map ``ValidationError.errors()`` items to ``{"field", "msg"}`` in Spanish."""
    return [_one(e) for e in errors]
