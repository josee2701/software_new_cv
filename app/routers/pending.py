"""Endpoints from spec §6 that belong to later phases: 501 until implemented.

Nothing is pending right now: the last one (``POST /api/assets``) moved to
:mod:`app.routers.assets`. The empty router stays so a future phase can park a 501 here again.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["pending"])
