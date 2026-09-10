"""``photo.*`` rules (spec §9.2): photo in the ``mail`` destination."""

from __future__ import annotations

from validator.registry import rule
from validator.types import Hit, RuleContext

# Countries where a photo in the CV is customary (LatAm, Spain, Germany, France).
PHOTO_COUNTRIES = frozenset(
    {
        "AR",
        "BO",
        "BR",
        "CL",
        "CO",
        "CR",
        "CU",
        "DO",
        "EC",
        "SV",
        "GT",
        "HN",
        "MX",
        "NI",
        "PA",
        "PY",
        "PE",
        "PR",
        "UY",
        "VE",
        "ES",
        "DE",
        "FR",
    }
)


def includes_photo(ctx: RuleContext) -> bool:
    return ctx.profile.include_photo and ctx.cv.basics.photo_asset_id is not None


@rule(
    id="photo.present_mail",
    section="basics",
    severity={"ats": "-", "mail": "info"},
    weight=1,
)
def present_mail(ctx: RuleContext) -> list[Hit]:
    """Destino Correo sin foto: sugerir agregarla."""
    if includes_photo(ctx):
        return []
    return [
        Hit(
            "La versión para correo no lleva foto.",
            entity="basics",
            suggestion="Agrega una foto profesional y actívala en el perfil Correo.",
        )
    ]


@rule(
    id="photo.warning_region",
    section="basics",
    severity={"ats": "-", "mail": "warning"},
    weight=2,
)
def warning_region(ctx: RuleContext) -> list[Hit]:
    """Foto en un país donde no es habitual (fuera de LatAm, ES, DE, FR)."""
    country = (ctx.cv.basics.country or "").upper()
    if not includes_photo(ctx) or country in PHOTO_COUNTRIES:
        return []
    return [
        Hit(
            f"En tu país ({country or 'sin definir'}) no es habitual incluir foto en la hoja "
            "de vida.",
            entity="basics",
            suggestion="Considera exportar la versión sin foto.",
        )
    ]
