"""``docs/ATS_RULES.md`` generated from the registry (``cv-ats rules --md``, F3-06)."""

from __future__ import annotations

from models.enums import Destination
from validator.registry import RuleSpec, registered_rules
from validator.types import Phase

FAMILY_TITLES: dict[str, str] = {
    "contact": "Contacto",
    "structure": "Estructura",
    "content": "Contenido",
    "dates": "Fechas",
    "length": "Extensión",
    "technical": "Técnicas (PDF generado)",
    "photo": "Foto",
}


def _severity(spec: RuleSpec, destination: Destination) -> str:
    severity = spec.severity_for(destination)
    return severity.value if severity is not None else "–"


def _cell(text: str) -> str:
    return text.replace("``", "`").replace("|", "\\|")


def rules_markdown() -> str:
    """Markdown table of every registered rule, grouped by family."""
    specs = registered_rules()
    lines = [
        "# Reglas del validador ATS",
        "",
        "> Archivo generado con `uv run cv-ats rules --md` a partir del registro "
        "(`validator/rules/*`). No editar a mano.",
        "",
        "## Cómo se calcula el puntaje",
        "",
        "- Cada regla se ejecuta solo en los destinos con severidad "
        "(`–` = no corre en ese destino).",
        "- Una regla con hallazgos descuenta su peso **una sola vez** por reporte: "
        "error = peso, warning = peso / 2, info = 0. Puntaje = 100 - descuentos, "
        "redondeado hacia abajo, mínimo 0.",
        "- Fase `pre`: corre siempre (datos del CV, perfil, HTML y páginas si se conocen). "
        "Fase `post`: solo con el PDF generado (`PdfInfo`).",
        "- Destino `ats`: la exportación se bloquea con al menos un error. `mail` nunca bloquea.",
        "",
        f"Total: {len(specs)} reglas.",
    ]
    families: dict[str, list[RuleSpec]] = {}
    for spec in specs:
        families.setdefault(spec.id.split(".", 1)[0], []).append(spec)
    order = list(FAMILY_TITLES) + sorted(set(families) - set(FAMILY_TITLES))
    for family in order:
        if family not in families:
            continue
        lines += [
            "",
            f"## {FAMILY_TITLES.get(family, family)}",
            "",
            "| id | Sección | ats | mail | Peso | Fase | Descripción |",
            "|---|---|---|---|---|---|---|",
        ]
        for spec in families[family]:
            phase = "post" if spec.phase is Phase.POST else "pre"
            lines.append(
                f"| `{spec.id}` | {spec.section} | {_severity(spec, Destination.ATS)} | "
                f"{_severity(spec, Destination.MAIL)} | {spec.weight} | {phase} | "
                f"{_cell(spec.description)} |"
            )
    return "\n".join(lines) + "\n"
