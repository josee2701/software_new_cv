from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import SessionDep
from schemas import TechnologyOut
from services import TechnologyService

router = APIRouter(tags=["technologies"])


@router.get("/technologies", response_model=list[TechnologyOut])
def search_technologies(
    session: SessionDep,
    q: Annotated[str, Query(max_length=60)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[TechnologyOut]:
    """Autocomplete: one entry per canonical name, prefix matches first."""
    return [TechnologyOut.model_validate(t) for t in TechnologyService(session).search(q, limit)]
