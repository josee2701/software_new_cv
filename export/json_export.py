"""JSON export: ``ResumeOut.model_dump(mode="json")`` (spec §10 step 8)."""

from __future__ import annotations

import json
from typing import Any

from schemas import ResumeOut


def to_dict(cv: ResumeOut) -> dict[str, Any]:
    return cv.model_dump(mode="json")


def to_json_bytes(cv: ResumeOut) -> bytes:
    """UTF-8 JSON (accents kept, indented) of the full resume tree."""
    return json.dumps(to_dict(cv), ensure_ascii=False, indent=2).encode("utf-8")
