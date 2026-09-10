"""Renderiza las plantillas de render/templates con el contexto de muestra (herramienta de Diseño).

Genera HTML y PDF por plantilla/tema/densidad en docs/design/out/, imprime el número de páginas y
hace un round-trip rápido con pdfplumber (email, teléfono y empresas en el texto extraído).

Uso:
    uv run python docs/design/render_sample.py            # es + en
    uv run python docs/design/render_sample.py --lang es
"""

from __future__ import annotations

import argparse
import base64
import copy
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

ROOT = Path(__file__).resolve().parents[2]
DESIGN_DIR = ROOT / "docs" / "design"
OUT_DIR = DESIGN_DIR / "out"
TEMPLATES_DIR = ROOT / "render" / "templates"
I18N_DIR = ROOT / "web" / "i18n"
PHOTO = DESIGN_DIR / "sample_photo.png"

THEMES = ("slate", "ocean", "graphite")
DENSITIES = ("compact", "normal", "wide")
EN_SLUGS = ("ats_normal", "mail_slate_foto", "mail_ocean_sinfoto")  # subconjunto en inglés
SIDEBAR_RATIO = 0.32  # ancho de la sidebar del mail (grid 32% / 68%)


@dataclass(frozen=True)
class Variant:
    """Una combinación de perfil a renderizar."""

    slug: str
    destination: str
    density: str = "normal"
    font: str = "Arial"
    theme: str | None = None
    photo: bool = False
    accent: str | None = None


def load_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def photo_data_uri() -> str:
    encoded = base64.b64encode(PHOTO.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_context(base: dict[str, Any], variant: Variant) -> dict[str, Any]:
    """Deriva el contexto de una variante a partir del fixture (que es un contexto ats)."""
    ctx = copy.deepcopy(base)
    i18n = load_json(I18N_DIR / f"{ctx['lang']}.json")
    title_kind = "upper" if variant.destination == "ats" else "title"
    is_mail = variant.destination == "mail"

    ctx["destination"] = variant.destination
    ctx["profile"].update(
        name="Correo" if is_mail else "Plataforma",
        theme=variant.theme,
        accent_color=variant.accent,
        density=variant.density,
        font_family=variant.font,
        include_photo=is_mail and variant.photo,
    )
    ctx["basics"]["photo_src"] = photo_data_uri() if is_mail and variant.photo else None
    for section in ctx["sections"]:
        section["title"] = i18n["sections"][section["key"]][title_kind]
    ctx["sections_by_key"] = {section["key"]: section for section in ctx["sections"]}
    return ctx


def variants() -> list[Variant]:
    items = [Variant(f"ats_{density}", "ats", density=density) for density in DENSITIES]
    items += [
        Variant("ats_normal_calibri", "ats", font="Calibri"),
        Variant("ats_normal_georgia", "ats", font="Georgia"),
    ]
    for theme in THEMES:
        for density in DENSITIES:
            suffix = "" if density == "normal" else f"_{density}"
            items.append(
                Variant(f"mail_{theme}{suffix}_foto", "mail", density, theme=theme, photo=True)
            )
            items.append(Variant(f"mail_{theme}{suffix}_sinfoto", "mail", density, theme=theme))
    items.append(
        Variant("mail_slate_accent_foto", "mail", theme="slate", photo=True, accent="#B4432F")
    )
    return items


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def languages_split(pages_text: list[str], ctx: dict[str, Any]) -> list[str]:
    """Idiomas en una página distinta a la de su título (bloque partido o título huérfano).

    En mail recibe solo el texto de la sidebar: pdfplumber une en una línea lo que está a la
    misma altura en las dos columnas.
    """
    section = ctx["sections_by_key"].get("languages")
    if section is None:
        return []
    title = section["title"].upper()  # ats ya viene en mayúsculas; mail lo pone el CSS
    title_pages = [
        index
        for index, text in enumerate(pages_text)
        if any(line.strip() == title for line in text.splitlines())
    ]
    if len(title_pages) != 1:
        return [f"título {title!r} encontrado en páginas {title_pages}"]
    page_text = pages_text[title_pages[0]]
    return [
        f"idioma {entry['name']!r} fuera de la página del título {title!r}"
        for entry in section["entries"]
        if entry["name"] not in page_text
    ]


def roundtrip(pdf_path: Path, ctx: dict[str, Any]) -> list[str]:
    """Devuelve problemas de extracción: valores ausentes y bloques de idiomas partidos."""
    with pdfplumber.open(pdf_path) as pdf:
        pages_text = [page.extract_text() or "" for page in pdf.pages]
        if ctx["destination"] == "mail":
            block_text = [
                page.crop((0, 0, page.width * SIDEBAR_RATIO, page.height)).extract_text() or ""
                for page in pdf.pages
            ]
        else:
            block_text = pages_text
    text = normalize(" ".join(pages_text))
    compact = re.sub(r"\s", "", text)
    basics = ctx["basics"]
    missing: list[str] = []
    folded = text.casefold()
    for needle in (basics["email"], basics["phone_display"], basics["full_name"]):
        if needle.casefold() not in folded:
            missing.append(needle)
    if basics["phone"] not in compact:
        missing.append(f"{basics['phone']} (E.164 sin espacios)")
    experience = ctx["sections_by_key"].get("experience", {"entries": []})
    for item in experience["entries"]:
        if item["company"] not in text:
            missing.append(item["company"])
    return missing + languages_split(block_text, ctx)


def html_violations(html: str) -> list[str]:
    lowered = html.lower()
    return [tag for tag in ("<table", "<img", "<svg", "position: absolute") if tag in lowered]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=("es", "en", "all"), default="all")
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="carpeta de salida")
    args = parser.parse_args()
    out_dir: Path = args.out
    langs = ("es", "en") if args.lang == "all" else (args.lang,)

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    failures = 0

    print(f"{'archivo':<34} {'págs':>4}  round-trip")
    for lang in langs:
        base = load_json(DESIGN_DIR / f"sample_context_{lang}.json")
        for variant in variants():
            if lang == "en" and variant.slug not in EN_SLUGS:
                continue
            ctx = build_context(base, variant)
            html = env.get_template(f"{variant.destination}/base.html").render(**ctx)
            stem = f"{variant.slug}_{lang}"
            (out_dir / f"{stem}.html").write_text(html, encoding="utf-8")

            document = HTML(string=html, base_url=str(ROOT)).render()
            pdf_path = out_dir / f"{stem}.pdf"
            # Un solo write: en el disco NTFS (ntfs3) la escritura incremental de WeasyPrint
            # llegó a quedarse bloqueada en estado D.
            pdf_path.write_bytes(document.write_pdf())

            problems = roundtrip(pdf_path, ctx)
            if variant.destination == "ats":
                problems += [f"HTML contiene {tag}" for tag in html_violations(html)]
                if variant.density == "normal" and not 1 <= len(document.pages) <= 2:
                    problems.append(f"{len(document.pages)} páginas (se esperan 1 a 2)")
            failures += bool(problems)
            status = "OK" if not problems else "FALLA: " + "; ".join(problems)
            print(f"{stem:<34} {len(document.pages):>4}  {status}")

    print(f"\nSalida en {out_dir}/")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
