"""Jinja environment, form helpers and HTML responses for the ``/ui`` editor.

Contract: ``docs/design/EDITOR_CONTEXT.md`` §1 and §2. This environment is independent from the
one used by ``render/`` (different loader, filters and globals).
"""

from __future__ import annotations

import functools
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

from fastapi import Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ValidationError
from starlette.datastructures import FormData

from app.config import PROJECT_ROOT
from models.enums import ShowIn
from render.filters import MONTHS
from schemas.errors import to_field_errors
from services.errors import ConflictError, InvalidDataError, NotFoundError

WEB_DIR = PROJECT_ROOT / "web"
STATIC_URL = "/static"
UI_LANG = "es"
#: ``cv-changed`` makes the toolbar reload the preview (contract §6).
CV_CHANGED = {"HX-Trigger": "cv-changed"}

# --------------------------------------------------------------------------------- filters


def _as_date(value: Any) -> date | None:
    """Tolerate the raw form strings kept in a 422 re-paint (``"2024-03"``)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        parts = raw.split("-")
        try:
            year, month = int(parts[0]), int(parts[1]) if len(parts) > 1 else 1
            return date(year, month, 1)
        except (ValueError, IndexError):
            return None
    return None


def ym(value: Any) -> str:
    """``date | None`` → ``"2024-03"`` (value of an ``<input type="month">``)."""
    parsed = _as_date(value)
    return "" if parsed is None else f"{parsed.year:04d}-{parsed.month:02d}"


def mdate(value: Any) -> str:
    """``date | None`` → ``"mar 2024"`` (item header summary)."""
    parsed = _as_date(value)
    if parsed is None:
        return ""
    return f"{MONTHS[UI_LANG][parsed.month - 1]} {parsed.year}"


def dt(value: Any) -> str:
    """``datetime`` → ``"10 sep 2026, 15:04"`` (resume list, local time)."""
    if not isinstance(value, datetime):
        return ""
    local = value.astimezone() if value.tzinfo is not None else value
    return f"{local.day} {MONTHS[UI_LANG][local.month - 1]} {local.year}, {local:%H:%M}"


# --------------------------------------------------------------------------------- choices

#: Blocks of ``choices`` expected by the templates (contract §1).
CHOICE_KEYS = (
    "show_in",
    "link_kind",
    "degree_level",
    "skill_level",
    "language_level",
    "employment_type",
    "destination",
    "density",
    "theme",
    "ats_font",
    "date_format",
    "max_pages",
    "section_key",
    "export_format",
)


def load_choices(path: Path | None = None) -> dict[str, list[dict[str, str]]]:
    """``{name: [{"value", "label"}, ...]}`` from ``web/i18n/ui_es.json``, keeping its order."""
    source = path or WEB_DIR / "i18n" / "ui_es.json"
    raw = json.loads(source.read_text(encoding="utf-8"))["choices"]
    return {
        name: [{"value": str(k), "label": str(v)} for k, v in labels.items()]
        for name, labels in raw.items()
    }


# --------------------------------------------------------------------------------- environment


def build_env(web_dir: Path | None = None) -> Environment:
    env = Environment(
        loader=FileSystemLoader(web_dir or WEB_DIR),
        autoescape=select_autoescape(default_for_string=True, default=True),
    )
    env.filters["ym"] = ym
    env.filters["mdate"] = mdate
    env.filters["dt"] = dt
    env.globals["static_url"] = STATIC_URL
    env.globals["choices"] = load_choices()
    return env


_env: Environment | None = None


def get_env() -> Environment:
    global _env
    if _env is None:
        _env = build_env()
    return _env


# --------------------------------------------------------------------------------- responses


def html(template: str, context: Mapping[str, Any], *, status: int = 200) -> HTMLResponse:
    body = get_env().get_template(template).render(**context)
    return HTMLResponse(body, status_code=status)


def written(template: str, context: Mapping[str, Any]) -> HTMLResponse:
    """200 + ``HX-Trigger: cv-changed`` (contract §2.2, successful write with a partial)."""
    body = get_env().get_template(template).render(**context)
    return HTMLResponse(body, headers=CV_CHANGED)


def invalid(template: str, context: Mapping[str, Any]) -> HTMLResponse:
    """422 re-painting the same partial (no ``HX-Trigger``: nothing changed)."""
    return html(template, context, status=422)


def deleted() -> Response:
    """200 with an empty body + ``cv-changed`` (contract §2.2, item deletion)."""
    return Response(content=b"", media_type="text/html", headers=CV_CHANGED)


def redirect(url: str) -> Response:
    """200 with an empty body and ``HX-Redirect`` (contract §2.2)."""
    return Response(content=b"", media_type="text/html", headers={"HX-Redirect": url})


# --------------------------------------------------------------------------------- forms

#: Form fields that keep every occurrence instead of "last one wins" (contract §2.1).
LIST_FIELDS = frozenset({"formats"})


class UiValidationError(Exception):
    """Field errors of a form, ready for the ``errors`` variable of a partial."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


@dataclass(frozen=True)
class Form:
    """Parsed ``application/x-www-form-urlencoded`` body (contract §2.1)."""

    values: dict[str, Any] = field(default_factory=dict)
    open: bool = False

    def to_model[S: BaseModel](self, schema: type[S]) -> S:
        return form_to_model(self, schema)


def read_form(form: FormData) -> Form:
    """Missing key → absent · ``""`` → None · repeated → last wins (``formats``: list)."""
    raw: dict[str, Any] = {}
    for key, value in form.multi_items():
        if not isinstance(value, str):
            continue  # uploads are read apart (``request.form()`` keeps them as UploadFile)
        if key in LIST_FIELDS:
            raw.setdefault(key, []).append(value)
        else:
            raw[key] = value
    is_open = raw.pop("_open", None) == "1"
    values = {k: (None if v == "" else v) for k, v in raw.items()}
    return Form(values=values, open=is_open)


def field_errors(exc: ValidationError | InvalidDataError) -> dict[str, str]:
    """``{campo: mensaje}`` keyed by the **last** segment of ``field`` (contract §2.2)."""
    items = exc.errors if isinstance(exc, InvalidDataError) else to_field_errors(exc.errors())
    out: dict[str, str] = {}
    for item in items:
        name = item["field"].rsplit(".", 1)[-1] or item["field"]
        out.setdefault(name, item["msg"])
    return out


def _is_int_literal(annotation: Any) -> bool:
    """``Literal[1, 2, 3]`` (also inside a union): Pydantic does not coerce ``"2"`` for it."""
    candidates = [annotation, *get_args(annotation)]
    return any(
        get_origin(c) is Literal and all(isinstance(a, int) for a in get_args(c))
        for c in candidates
    )


def coerce_for(schema: type[BaseModel], values: Mapping[str, Any]) -> dict[str, Any]:
    """Cast the digit strings of integer ``Literal`` fields (``max_pages``) to ``int``."""
    out = dict(values)
    for name, info in schema.model_fields.items():
        value = out.get(name)
        if isinstance(value, str) and value.isdigit() and _is_int_literal(info.annotation):
            out[name] = int(value)
    return out


def form_to_model[S: BaseModel](form: Form, schema: type[S]) -> S:
    """Validate the form values with ``schema``, raising :class:`UiValidationError`."""
    try:
        return schema.model_validate(coerce_for(schema, form.values))
    except ValidationError as exc:
        raise UiValidationError(field_errors(exc)) from exc


def merged(current: BaseModel | Mapping[str, Any], values: Mapping[str, Any]) -> dict[str, Any]:
    """``{**item, **enviado}`` as a dict so the 422 re-paint keeps what the user typed.

    Values of boolean fields arrive as ``"true"``/``"false"``: they are coerced so the
    checkboxes of the partial keep their state.
    """
    base = dict(current) if isinstance(current, Mapping) else current.model_dump()
    out = dict(base)
    for name, value in values.items():
        if isinstance(base.get(name), bool) and isinstance(value, str):
            out[name] = value == "true"
        else:
            out[name] = value
    return out


# --------------------------------------------------------------------------------- drafts


def _is_list(annotation: Any) -> bool:
    """True for ``list[X]`` and for unions that contain one."""
    if get_origin(annotation) is list:
        return True
    return any(get_origin(arg) is list for arg in get_args(annotation))


def draft(out_schema: type[BaseModel], **overrides: Any) -> dict[str, Any]:
    """Unsaved item (contract §4.3): every key of the ``*Out``, ``id=None``, lists empty."""
    values: dict[str, Any] = {}
    for name, info in out_schema.model_fields.items():
        if name == "id":
            values[name] = None
        elif name == "position":
            values[name] = 0
        elif name == "show_in":
            values[name] = ShowIn.BOTH
        elif info.annotation is bool:
            values[name] = False
        elif _is_list(info.annotation):
            values[name] = []
        else:
            values[name] = None
    values.update(overrides)
    return values


# --------------------------------------------------------------------------------- errors


def ui_errors[**P](
    fn: Callable[P, Awaitable[Response]],
) -> Callable[P, Awaitable[Response]]:
    """Map domain errors of a ``/ui`` endpoint to plain text in Spanish (contract §2.2)."""

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Response:
        try:
            return await fn(*args, **kwargs)
        except NotFoundError as exc:
            return PlainTextResponse(exc.message, status_code=404)
        except ConflictError as exc:
            return PlainTextResponse(exc.message, status_code=409)
        except UiValidationError as exc:
            return PlainTextResponse(str(exc), status_code=422)
        except InvalidDataError as exc:
            return PlainTextResponse(exc.message, status_code=422)

    return wrapper
