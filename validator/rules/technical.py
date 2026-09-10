"""``technical.*`` rules (spec §9.2, §9.3): checks on the generated PDF (``Phase.POST``).

They are pure functions over ``ctx.pdf`` (:class:`validator.types.PdfInfo`), produced by
``export/verify.py``; the engine only runs them when ``ctx.pdf`` is present.
"""

from __future__ import annotations

import re

from validator.registry import rule
from validator.text import fold
from validator.types import Hit, PdfInfo, Phase, RuleContext

MIN_COVERAGE = 0.95
_FILENAME_RE = re.compile(r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+_CV(?:_[A-Za-z0-9]+)*\.[A-Za-z0-9]+$")
_NAME_PARTICLES = {"de", "del", "la", "las", "los", "y"}


def _pdf(ctx: RuleContext) -> PdfInfo:
    assert ctx.pdf is not None  # POST rules only run with a PDF
    return ctx.pdf


def _norm_name(value: str | None) -> str:
    return " ".join(fold(value or "").split())


@rule(
    id="technical.text_extractable",
    section="pdf",
    severity={"ats": "error", "mail": "warning"},
    weight=20,
    phase=Phase.POST,
)
def text_extractable(ctx: RuleContext) -> list[Hit]:
    """Round-trip: ≥ 95% de los tokens del CV en el texto extraído; email y teléfono presentes."""
    pdf = _pdf(ctx)
    if not pdf.has_text:
        return [
            Hit(
                "El PDF no tiene texto extraíble (parece una imagen).",
                suggestion="Exporta con texto real; nunca un PDF rasterizado.",
            )
        ]
    hits: list[Hit] = []
    if pdf.coverage < MIN_COVERAGE:
        missing = ", ".join(pdf.missing_tokens[:8])
        hits.append(
            Hit(
                f"Solo el {pdf.coverage:.0%} del contenido se recupera del PDF"
                + (f" (faltan: {missing})." if missing else "."),
                suggestion="Evita caracteres especiales, texto en imágenes o fuentes sin mapa "
                "de caracteres.",
            )
        )
    if not pdf.email_found:
        hits.append(
            Hit(
                "El correo no se encuentra en el texto del PDF.",
                entity="basics",
                suggestion="Muestra el correo como texto plano.",
            )
        )
    if not pdf.phone_found:
        hits.append(
            Hit(
                "El teléfono no se encuentra en el texto del PDF.",
                entity="basics",
                suggestion="Muestra el teléfono como texto plano.",
            )
        )
    return hits


@rule(
    id="technical.fonts_embedded",
    section="pdf",
    severity={"ats": "error", "mail": "info"},
    weight=5,
    phase=Phase.POST,
)
def fonts_embedded(ctx: RuleContext) -> list[Hit]:
    """Todas las fuentes embebidas en el PDF."""
    pdf = _pdf(ctx)
    if pdf.fonts_embedded:
        return []
    fonts = ", ".join(pdf.fonts[:6])
    return [
        Hit(
            "El PDF tiene fuentes sin embeber" + (f" ({fonts})." if fonts else "."),
            suggestion="Usa fuentes instaladas que el motor PDF pueda embeber.",
        )
    ]


@rule(
    id="technical.no_special_chars",
    section="pdf",
    severity={"ats": "warning", "mail": "-"},
    weight=3,
    phase=Phase.POST,
)
def no_special_chars(ctx: RuleContext) -> list[Hit]:
    """Sin caracteres fuera de Latin-1 + símbolos comunes (•, –, —, ·)."""
    chars = _pdf(ctx).non_latin1_chars
    if not chars:
        return []
    return [
        Hit(
            "El PDF contiene caracteres especiales: " + " ".join(chars[:10]) + ".",
            suggestion="Reemplázalos por letras, números o símbolos comunes.",
        )
    ]


def expected_name_parts(full_name: str) -> list[str]:
    """ASCII words of the name without particles (``"Andrés de la Cruz"`` → andres, cruz)."""
    return [w for w in re.findall(r"[a-z0-9]+", fold(full_name)) if w not in _NAME_PARTICLES]


@rule(
    id="technical.filename",
    section="export",
    severity={"ats": "warning", "mail": "warning"},
    weight=1,
    phase=Phase.POST,
)
def filename(ctx: RuleContext) -> list[Hit]:
    """Nombre de archivo ``Nombre_Apellido_CV...`` sin espacios ni tildes."""
    name = _pdf(ctx).filename
    if not name:
        return []
    hit = Hit(
        f"El nombre de archivo «{name}» no sigue el formato Nombre_Apellido_CV.",
        suggestion="Usa Nombre_Apellido_CV.pdf, sin espacios ni tildes.",
    )
    if not _FILENAME_RE.match(name):
        return [hit]
    parts = expected_name_parts(ctx.cv.basics.full_name)
    first = name.split("_", 1)[0].lower()
    if parts and first != parts[0]:
        return [hit]
    return []


@rule(
    id="technical.metadata",
    section="pdf",
    severity={"ats": "info", "mail": "info"},
    weight=1,
    phase=Phase.POST,
)
def metadata(ctx: RuleContext) -> list[Hit]:
    """Título y autor del PDF con el nombre de la persona."""
    pdf = _pdf(ctx)
    full_name = _norm_name(ctx.cv.basics.full_name)
    if not full_name:
        return []
    problems = []
    if _norm_name(pdf.author) != full_name:
        problems.append("autor")
    if full_name not in _norm_name(pdf.title):
        problems.append("título")
    if not problems:
        return []
    return [
        Hit(
            "Metadatos del PDF sin el nombre: " + " y ".join(problems) + ".",
            suggestion="El título y el autor del PDF deben llevar tu nombre completo.",
        )
    ]
