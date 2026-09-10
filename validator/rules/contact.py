"""``contact.*`` rules (spec §9.2): email, phone, location, LinkedIn, visible URLs."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from pydantic.networks import validate_email
from pydantic_core import PydanticCustomError

from models.enums import LinkKind
from validator.registry import rule
from validator.text import fold, html_anchors
from validator.types import Hit, RuleContext

E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def phone_digits(value: str) -> str:
    """Digits only (phones are compared on digits, see RENDER_CONTEXT.md)."""
    return re.sub(r"\D", "", value or "")


@rule(
    id="contact.email_present",
    section="basics",
    severity={"ats": "error", "mail": "error"},
    weight=15,
)
def email_present(ctx: RuleContext) -> list[Hit]:
    """Email obligatorio y válido."""
    email = (ctx.cv.basics.email or "").strip()
    if not email:
        return [
            Hit(
                "Falta el correo electrónico.",
                entity="basics",
                suggestion="Agrega un correo profesional (nombre.apellido@dominio).",
            )
        ]
    try:
        validate_email(email)
    except PydanticCustomError:
        return [
            Hit(
                f"El correo «{email}» no es válido.",
                entity="basics",
                suggestion="Corrige el correo electrónico.",
            )
        ]
    return []


@rule(
    id="contact.phone_present",
    section="basics",
    severity={"ats": "error", "mail": "warning"},
    weight=10,
)
def phone_present(ctx: RuleContext) -> list[Hit]:
    """Teléfono presente en formato internacional E.164 (+57...)."""
    phone = (ctx.cv.basics.phone or "").strip()
    if not phone_digits(phone):
        return [
            Hit(
                "Falta el teléfono.",
                entity="basics",
                suggestion="Agrega un teléfono con indicativo, p. ej. +57 300 123 4567.",
            )
        ]
    if not E164_RE.match(phone):
        return [
            Hit(
                f"El teléfono «{phone}» no está en formato internacional.",
                entity="basics",
                suggestion="Usa el formato internacional con indicativo, p. ej. +57 300 123 4567.",
            )
        ]
    return []


@rule(
    id="contact.location_present",
    section="basics",
    severity={"ats": "warning", "mail": "info"},
    weight=3,
)
def location_present(ctx: RuleContext) -> list[Hit]:
    """Ciudad y país presentes."""
    basics = ctx.cv.basics
    missing = [
        label
        for label, value in (("ciudad", basics.city), ("país", basics.country))
        if not (value or "").strip()
    ]
    if not missing:
        return []
    return [
        Hit(
            "Falta la ubicación: " + " y ".join(missing) + ".",
            entity="basics",
            suggestion="Indica ciudad y país: muchos ATS filtran candidatos por ubicación.",
        )
    ]


@rule(
    id="contact.linkedin_present",
    section="links",
    severity={"ats": "warning", "mail": "info"},
    weight=3,
)
def linkedin_present(ctx: RuleContext) -> list[Hit]:
    """Perfil de LinkedIn recomendado."""
    if any(link.kind is LinkKind.LINKEDIN for link in ctx.cv.links):
        return []
    return [
        Hit(
            "No hay enlace a LinkedIn.",
            entity="contact_link",
            suggestion="Agrega la URL de tu perfil de LinkedIn.",
        )
    ]


def _host(url: str) -> str:
    host = urlsplit(url if "://" in url else f"https://{url}").hostname or ""
    return fold(host.removeprefix("www."))


@rule(
    id="contact.url_plain",
    section="links",
    severity={"ats": "error", "mail": "-"},
    weight=5,
)
def url_plain(ctx: RuleContext) -> list[Hit]:
    """Las URLs deben ser texto visible (no solo un hipervínculo «aquí»). Se verifica en el HTML."""
    if ctx.html is None:
        return []
    hits: list[Hit] = []
    for href, text in html_anchors(ctx.html):
        if not href.lower().startswith(("http://", "https://")):
            continue
        host = _host(href)
        if host and host in fold(text):
            continue
        link = next((lk for lk in ctx.cv.links if lk.url == href), None)
        hits.append(
            Hit(
                f"El enlace a {host or href} se muestra como «{text or '(vacío)'}» "
                "en vez de la URL.",
                entity="contact_link" if link else None,
                entity_id=link.id if link else None,
                suggestion="Muestra la URL como texto (p. ej. linkedin.com/in/usuario).",
            )
        )
    return hits
