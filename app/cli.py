"""Command line interface (Typer): ``cv-ats <command>`` (spec §13)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

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
    """Valida un CV contra un perfil (lo guarda como reporte). Sale con 1 si bloquea (ats)."""
    from app.db import get_sessionmaker
    from models.enums import Destination
    from services import ProfileService
    from services.errors import DomainError
    from services.validation import ValidationService

    with get_sessionmaker()() as session:
        try:
            profile_id = _resolve_profile(session, resume, profile)
            report = ValidationService(session).run_and_save(resume, profile_id, render_html=True)
            destination = ProfileService(session).get(profile_id).destination
        except DomainError as exc:
            typer.echo(exc.message, err=True)
            raise typer.Exit(code=2) from exc
    if json:
        typer.echo(report.model_dump_json(indent=2))
    else:
        typer.echo(
            f"Reporte #{report.id} · puntaje {report.score} · "
            f"{report.errors} errores · {report.warnings} advertencias"
        )
        for finding in report.findings:
            typer.echo(f"  [{finding.severity.value}] {finding.rule_id}: {finding.message}")
            if finding.suggestion:
                typer.echo(f"      → {finding.suggestion}")
    if destination is Destination.ATS and report.errors:
        raise typer.Exit(code=1)


def _resolve_profile(session: Any, resume_id: int, name: str) -> int:
    """Profile id by name (case-insensitive) or by destination ("ats" / "mail")."""
    from services import ProfileService

    profiles = ProfileService(session).list(resume_id)
    wanted = name.strip().lower()
    for profile in profiles:
        if profile.name.lower() == wanted:
            return profile.id
    for profile in profiles:
        if profile.destination.value == wanted:
            return profile.id
    raise typer.BadParameter(f"El CV {resume_id} no tiene un perfil llamado '{name}'")


@app.command()
def export(
    resume: Annotated[int, typer.Option(help="Id del CV")],
    profile: Annotated[str, typer.Option(help="Nombre del perfil (o ats | mail)")],
    format: Annotated[str, typer.Option("--format", help="pdf,docx,json")] = "pdf",
    out: Annotated[Path, typer.Option(help="Carpeta de salida")] = Path("out"),
    photo_variant: Annotated[
        bool, typer.Option(help="En correo, generar también la versión sin foto")
    ] = False,
) -> None:
    """Exporta un CV (valida, genera archivos y copia el resultado a --out)."""
    import shutil

    from app.db import get_sessionmaker
    from models.enums import ExportFormat, ExportStatus
    from services.export import ExportService

    try:
        formats = [ExportFormat(f.strip().lower()) for f in format.split(",") if f.strip()]
    except ValueError as exc:
        raise typer.BadParameter("Formatos válidos: pdf, docx, json") from exc
    with get_sessionmaker()() as session:
        profile_id = _resolve_profile(session, resume, profile)
        outcome = ExportService(session).run(resume, profile_id, formats, photo_variant)
        job = outcome.job
        typer.echo(f"Exportación #{job.id}: {job.status.value}")
        if outcome.report is not None:
            r = outcome.report
            typer.echo(f"Puntaje: {r.score} ({r.errors} errores, {r.warnings} advertencias)")
            for finding in r.findings:
                typer.echo(f"  [{finding.severity.value}] {finding.rule_id}: {finding.message}")
        if outcome.pdf_info is not None:
            info = outcome.pdf_info
            typer.echo(f"Páginas: {info.pages} · cobertura: {info.coverage:.1%}")
        if job.error:
            typer.echo(job.error, err=True)
        out.mkdir(parents=True, exist_ok=True)
        for path in outcome.files:
            shutil.copy2(path, out / path.name)
            typer.echo(f"  → {out / path.name}")
        if job.status is not ExportStatus.DONE:
            raise typer.Exit(code=1)


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
    """Restaura una versión (snapshot) sobre su CV."""
    from app.db import get_sessionmaker
    from services import ResumeService

    with get_sessionmaker()() as session:
        resume = ResumeService(session).restore_snapshot(snapshot)
        typer.echo(f"CV {resume.id} restaurado desde la versión {snapshot}.")


@app.command()
def rules(
    md: Annotated[bool, typer.Option("--md", help="Genera el Markdown de las reglas")] = False,
    out: Annotated[Path, typer.Option(help="Archivo destino de --md")] = (
        PROJECT_ROOT / "docs" / "ATS_RULES.md"
    ),
) -> None:
    """Lista las reglas del validador; con --md genera docs/ATS_RULES.md."""
    from models.enums import Destination
    from validator.docs import rules_markdown
    from validator.registry import registered_rules

    if md:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rules_markdown(), encoding="utf-8")
        typer.echo(f"Reglas escritas en {out}")
        return
    for spec in registered_rules():
        levels = " ".join(
            f"{d.value}={s.value if (s := spec.severity_for(d)) else '-'}" for d in Destination
        )
        typer.echo(f"{spec.id:34} {levels:24} peso={spec.weight} fase={spec.phase.value}")


def main() -> None:
    app()
