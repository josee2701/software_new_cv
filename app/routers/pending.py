"""Endpoints from spec §6 that belong to later phases: 501 until implemented."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["pending"])

_PENDING = "No implementado todavía"


def _not_implemented() -> None:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, _PENDING)


@router.post("/assets", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def upload_asset() -> None:
    _not_implemented()
