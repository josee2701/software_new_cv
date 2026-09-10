"""Shared fixtures: in-memory SQLite with foreign keys ON."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.db  # noqa: F401  (registers the PRAGMA foreign_keys listener)
import models


@pytest.fixture(autouse=True)
def _isolated_data_dir(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """Every test writes exports/uploads under a temporary DATA_DIR, never ``data/``."""
    from app.config import get_settings

    data_dir = tmp_path_factory.mktemp("data")
    monkeypatch.setenv("CV_ATS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CV_ATS_DB_URL", f"sqlite:///{data_dir / 'cv.db'}")
    get_settings.cache_clear()
    yield data_dir
    get_settings.cache_clear()


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as s:
        yield s
