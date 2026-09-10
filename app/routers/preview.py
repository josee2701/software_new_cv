"""HTML preview of a resume with a profile (``GET /api/resumes/{id}/preview``)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from jinja2 import TemplateNotFound

from app.deps import SessionDep
from models.enums import Density
from render.renderer import render
from schemas import ExportProfileOut
from services import ProfileService, ResumeService

router = APIRouter(tags=["preview"])


@router.get("/resumes/{resume_id}/preview", response_class=HTMLResponse)
def preview(
    resume_id: int,
    session: SessionDep,
    profile_id: Annotated[int | None, Query()] = None,
    density: Annotated[Density | None, Query()] = None,
    pages: Annotated[bool, Query(description="Contar páginas (header X-Pages)")] = True,
) -> HTMLResponse:
    """Rendered HTML with the estimated page count in the ``X-Pages`` header."""
    cv = ResumeService(session).get_out(resume_id)
    if profile_id is not None:
        profile = ExportProfileOut.model_validate(
            ProfileService(session).get(profile_id, resume_id)
        )
    elif cv.profiles:
        profile = cv.profiles[0]
    else:
        raise HTTPException(status.HTTP_409_CONFLICT, "El CV no tiene perfiles de exportación")
    if density is not None:
        profile = profile.model_copy(update={"density": density})
    try:
        result = render(cv, profile, for_preview=True, with_pages=pages)
    except TemplateNotFound as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Plantilla de render aún no disponible"
        ) from exc
    headers = {"X-Pages": str(result.pages)} if result.pages is not None else {}
    return HTMLResponse(result.html, headers=headers)
