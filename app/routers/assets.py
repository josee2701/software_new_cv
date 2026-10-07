"""``POST /api/assets`` (spec §6): upload a photo and get the ``asset`` row.

Shares the Pillow logic of :mod:`services.asset` with ``POST /ui/resumes/{id}/photo``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from app.deps import SessionDep
from schemas import AssetOut
from services.asset import AssetService

router = APIRouter(tags=["assets"])


@router.post("/assets", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def upload_asset(session: SessionDep, file: Annotated[UploadFile, File()]) -> AssetOut:
    """Validates mime and size, crops a centred square and stores the ``_400.jpg`` version."""
    asset = AssetService(session).create(await file.read(), file.filename or "foto.jpg")
    return AssetOut.model_validate(asset)
