"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import PROJECT_ROOT, get_settings
from app.routers import experiences, pending, preview, profiles, resumes, sections, technologies
from schemas.errors import to_field_errors
from services.errors import ConflictError, InvalidDataError, NotFoundError

API_PREFIX = "/api"


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": to_field_errors(exc.errors())},
        )

    @app.exception_handler(InvalidDataError)
    async def _invalid(_: Request, exc: InvalidDataError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": exc.errors}
        )

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": exc.message})

    @app.exception_handler(ConflictError)
    async def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": exc.message})


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.LOG_LEVEL.upper())
    app = FastAPI(
        title="cv-ats",
        version="0.1.0",
        description="Editor y validador de hojas de vida con exportación ATS y diseño",
    )
    for module in (resumes, experiences, sections, profiles, technologies, preview, pending):
        app.include_router(module.router, prefix=API_PREFIX)
    static_dir = PROJECT_ROOT / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    _register_error_handlers(app)
    return app
