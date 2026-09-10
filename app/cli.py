"""Command line interface (Typer): ``cv-ats <command>`` (spec §13)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from alembic.config import Config

from alembic import command
from app.config import PROJECT_ROOT, get_settings

app = typer.Typer(
    help="cv-ats: editor, validador y exportador de hojas de vida.", no_args_is_help=True
)

_NOT_IMPLEMENTED = "No implementado todavía."


def _alembic_config() -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().DB_URL)
    return cfg


def _pending(name: str) -> None:
    typer.echo(f"{name}: {_NOT_IMPLEMENTED}", err=True)
    raise typer.Exit(code=1)


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Interfaz de red")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Puerto")] = 8000,
    reload: Annotated[bool, typer.Option(help="Recargar al cambiar el código")] = False,
) -> None:
    """Inicia el servidor web (http://127.0.0.1:8000)."""
    import uvicorn

    uvicorn.run("app.main:create_app", factory=True, host=host, port=port, reload=reload)


@app.command()
def seed() -> None:
    """Aplica migraciones y carga tecnologías + CV de ejemplo (idempotente)."""
    from app.db import get_sessionmaker
    from app.seed import run_seed

    command.upgrade(_alembic_config(), "head")
    with get_sessionmaker()() as session:
        result = run_seed(session)
    estado = "creado" if result.resume_created else "ya existía"
    typer.echo(
        f"Tecnologías nuevas: {result.technologies_created}. "
        f"CV de ejemplo (id={result.resume_id}): {estado}."
    )


@app.command()
def validate(
    resume: Annotated[int, typer.Option(help="Id del CV")],
    profile: Annotated[str, typer.Option(help="ats | mail | nombre del perfil")] = "ats",
    json: Annotated[bool, typer.Option("--json", help="Salida JSON")] = False,
) -> None:
    """Valida un CV contra un perfil."""
    _pending("validate")


@app.command()
def export(
    resume: Annotated[int, typer.Option(help="Id del CV")],
    profile: Annotated[str, typer.Option(help="Nombre del perfil")],
    format: Annotated[str, typer.Option("--format", help="pdf,docx,json")] = "pdf",
    out: Annotated[Path, typer.Option(help="Carpeta de salida")] = Path("out"),
) -> None:
    """Exporta un CV."""
    _pending("export")


@app.command(name="import")
def import_(
    file: Annotated[Path, typer.Argument(help="PDF o DOCX")],
    resume: Annotated[int, typer.Option(help="Id del CV")],
    apply: Annotated[bool, typer.Option(help="Aplicar sin revisar")] = False,
) -> None:
    """Importa un CV desde PDF/DOCX."""
    _pending("import")


@app.command()
def snapshot(
    resume: Annotated[int, typer.Option(help="Id del CV")],
    label: Annotated[str, typer.Option(help="Etiqueta de la versión")] = "",
) -> None:
    """Guarda una versión (snapshot) del CV."""
    from app.db import get_sessionmaker
    from services import ResumeService

    with get_sessionmaker()() as session:
        snap = ResumeService(session).create_snapshot(resume, label or None)
    typer.echo(f"Versión guardada (id={snap.id}).")


@app.command()
def restore(snapshot: Annotated[int, typer.Option(help="Id de la versión")]) -> None:
    """Restaura una versión (snapshot)."""
    _pending("restore")


def main() -> None:
    app()
