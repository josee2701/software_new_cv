"""Application settings (pydantic-settings).

Environment variables use the ``CV_ATS_`` prefix, e.g. ``CV_ATS_DB_URL``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CV_ATS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATA_DIR: Path = PROJECT_ROOT / "data"
    DB_URL: str = ""
    PDF_ENGINE: Literal["weasyprint", "playwright"] = "weasyprint"
    LOG_LEVEL: str = "INFO"

    @model_validator(mode="after")
    def _default_db_url(self) -> Settings:
        if not self.DB_URL:
            self.DB_URL = f"sqlite:///{self.DATA_DIR / 'cv.db'}"
        return self

    @property
    def uploads_dir(self) -> Path:
        return self.DATA_DIR / "uploads"

    @property
    def exports_dir(self) -> Path:
        return self.DATA_DIR / "exports"


@lru_cache
def get_settings() -> Settings:
    return Settings()
