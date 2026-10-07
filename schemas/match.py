"""Job posting match schemas (spec §12)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from schemas.common import InputModel, OptStr120, OutModel


class PostingCreate(InputModel):
    title: Annotated[str, Field(min_length=1, max_length=160)]
    company: OptStr120 = None
    raw_text: Annotated[str, Field(min_length=20, max_length=50_000)]


class PostingOut(OutModel):
    id: int
    resume_id: int
    title: str
    company: str | None
    created_at: datetime


class KeywordOut(BaseModel):
    keyword: str
    weight: float
    found_in_cv: bool
    technology: bool = False


class MatchResultOut(BaseModel):
    posting: PostingOut
    present: list[KeywordOut] = Field(default_factory=list)
    missing: list[KeywordOut] = Field(default_factory=list)
    coverage: float  # present / total keywords (0..1)
