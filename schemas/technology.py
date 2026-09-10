from __future__ import annotations

from schemas.common import OutModel


class TechnologyOut(OutModel):
    id: int
    name: str
    canonical: str
    category: str | None
