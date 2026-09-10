"""CLI end to end on a temporary database (seed, snapshot, restore, export)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

import services.export as export_service
from app.cli import app


@pytest.fixture
def cli_env(_isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from app.db import get_engine, get_sessionmaker

    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    monkeypatch.setattr(export_service, "default_engine", lambda: export_service.null_engine)
    yield _isolated_data_dir
    get_engine().dispose()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


def test_cli_seed_snapshot_restore_export(cli_env: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    first = runner.invoke(app, ["seed"])
    assert first.exit_code == 0, first.output
    assert "creado" in first.output
    again = runner.invoke(app, ["seed"])
    assert "Tecnologías nuevas: 0" in again.output and "ya existía" in again.output

    snap = runner.invoke(app, ["snapshot", "--resume", "1", "--label", "cli"])
    assert snap.exit_code == 0 and "id=1" in snap.output
    restored = runner.invoke(app, ["restore", "--snapshot", "1"])
    assert restored.exit_code == 0, restored.output

    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["export", "--resume", "1", "--profile", "plataforma", "--format", "pdf,json",
         "--out", str(out)],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in out.iterdir()) == [
        "Andres_Rojas_CV_ats.json", "Andres_Rojas_CV_ats.pdf",
    ]  # fmt: skip
    assert "done" in result.output

    bad = runner.invoke(app, ["export", "--resume", "1", "--profile", "nope"])
    assert bad.exit_code != 0
    bad_fmt = runner.invoke(app, ["export", "--resume", "1", "--profile", "ats", "--format", "x"])
    assert bad_fmt.exit_code != 0
