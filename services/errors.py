"""Domain errors raised by services and mapped to HTTP codes by the API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from schemas.errors import FieldError, to_field_errors


class DomainError(Exception):
    """Base class. ``message`` is user-facing (Spanish)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """→ HTTP 404."""


class ConflictError(DomainError):
    """Business-rule / integrity conflict → HTTP 409."""


class InvalidDataError(DomainError):
    """Field-level validation error detected in the service → HTTP 422."""

    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__("; ".join(f"{e['field']}: {e['msg']}" for e in errors))
        self.errors = errors

    @classmethod
    def single(cls, field: str, msg: str) -> InvalidDataError:
        return cls([FieldError(field=field, msg=msg)])


def validate_model[S: BaseModel](schema: type[S], data: dict[str, Any]) -> S:
    """Validate ``data`` with ``schema`` raising :class:`InvalidDataError` on failure."""
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise InvalidDataError(to_field_errors(exc.errors())) from exc
