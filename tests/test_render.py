"""Render context (show_in, order, dates es/en, titles) and HTML (spec §8, §14)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.seed import run_seed
from models.enums import Destination, SectionKey, ShowIn
from render.context import build_context, country_name
from render.filters import fmt_date, fmt_range, initials, phone_display, url_display, years_label
from render.renderer import TEMPLATES_DIR, RenderResult, render
from schemas import (
    AchievementUpdate,
    AssetOut,
    EducationUpdate,
    ExperienceUpdate,
    ExportProfileOut,
    ProfileSectionIn,
    ResumeOut,
    ResumeUpdate,
)
from services import EducationService, ExperienceService, ProfileService, ResumeService

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_ES = ROOT / "docs" / "design" / "sample_context_es.json"
HAS_ATS = (TEMPLATES_DIR / "ats" / "base.html").is_file()
HAS_MAIL = (TEMPLATES_DIR / "mail" / "base.html").is_file()


@pytest.fixture
def seeded(session: Session) -> int:
    return run_seed(session).resume_id


def _cv(session: Session, rid: int) -> ResumeOut:
    return ResumeService(session).get_out(rid)


def _profile(cv: ResumeOut, destination: Destination) -> ExportProfileOut:
    return next(p for p in cv.profiles if p.destination == destination)


def _ctx(session: Session, rid: int, destination: Destination) -> dict[str, Any]:
    cv = _cv(session, rid)
    return build_context(cv, _profile(cv, destination))


# ------------------------------------------------------------------------ filters


@pytest.mark.parametrize(
    ("fmt", "lang", "expected"),
    [
        ("MM/YYYY", "es", "01/2024"),
        ("MMM YYYY", "es", "ene 2024"),
        ("MMM YYYY", "en", "Jan 2024"),
        ("YYYY", "en", "2024"),
    ],
)
def test_fmt_date(fmt: str, lang: str, expected: str) -> None:
    assert fmt_date(date(2024, 1, 1), fmt, lang) == expected
    assert fmt_date(None, fmt, lang) == ""


def test_fmt_range() -> None:
    start, end = date(2021, 3, 1), date(2023, 8, 1)
    assert fmt_range(start, end, fmt="MM/YYYY", lang="es") == "03/2021 – 08/2023"
    assert (
        fmt_range(start, None, fmt="MM/YYYY", lang="es", open_label="Actual") == "03/2021 – Actual"
    )
    assert (
        fmt_range(start, None, fmt="MMM YYYY", lang="en", open_label="Present")
        == "Mar 2021 – Present"
    )
    assert fmt_range(date(2021, 1, 1), date(2021, 9, 1), fmt="YYYY", lang="es") == "2021"
    assert fmt_range(None, None, fmt="YYYY", lang="es") == ""
    assert fmt_range(start, None, fmt="YYYY", lang="es") == "2021"


def test_small_filters() -> None:
    assert phone_display("+573001234567") == "+57 300 123 4567"
    assert phone_display("+15551234567") == "+1 555 123 4567"
    assert phone_display("") == ""
    assert url_display("https://www.linkedin.com/in/ana/") == "linkedin.com/in/ana"
    assert url_display(None) == ""
    assert initials("Andrés Felipe Rojas Martínez") == "AR"
    assert initials("Santiago Restrepo Mejía") == "SR"
    assert initials("maría de los ángeles pérez") == "MÁ"
    assert initials("Juan de la Cruz Gómez Ruiz") == "JG"
    assert initials("Ángela") == "Á"
    assert initials("  ") == ""
    assert initials("Ana") == "A"
    assert initials("") == ""
    assert years_label(1, "1 año", "{n} años") == "1 año"
    assert years_label(6, "1 año", "{n} años") == "6 años"
    assert years_label(6, "1 year", "{n} years") == "6 years"
    assert years_label(None, "1 año", "{n} años") is None
    assert country_name("co", "es") == "Colombia"
    assert country_name("US", "es") == "Estados Unidos"
    assert country_name("US", "en") == "United States"
    assert country_name("ZZ", "en") == "ZZ"


# ------------------------------------------------------------------------ context


def test_context_shape_matches_design_sample(session: Session, seeded: int) -> None:
    if not SAMPLE_ES.is_file():
        pytest.skip("docs/design/sample_context_es.json no existe")
    sample = json.loads(SAMPLE_ES.read_text(encoding="utf-8"))
    ctx = _ctx(session, seeded, Destination.ATS)
    assert set(ctx) == set(sample)
    for key in ("profile", "t", "basics"):
        assert set(ctx[key]) == set(sample[key]), key
    assert set(ctx["links"][0]) == set(sample["links"][0])
    assert [s["key"] for s in ctx["sections"]] == [s["key"] for s in sample["sections"]]
    sample_sections = sample["sections_by_key"]
    for section in ctx["sections"]:
        assert set(section) == {"key", "title", "entries"}
        if section["entries"]:
            expected = set(sample_sections[section["key"]]["entries"][0])
            assert set(section["entries"][0]) == expected, section["key"]
    skill = ctx["sections_by_key"]["skills"]["entries"][0]["skills"][0]
    assert set(skill) == set(sample_sections["skills"]["entries"][0]["skills"][0])


def test_context_basics_and_links(session: Session, seeded: int) -> None:
    ctx = _ctx(session, seeded, Destination.ATS)
    basics = ctx["basics"]
    assert basics["phone"] == "+573001234567"
    assert basics["phone_display"] == "+57 300 123 4567"
    assert basics["location"] == "Bogotá, Cundinamarca, Colombia"
    assert basics["initials"] == "AR"
    assert basics["photo_src"] is None
    assert ctx["doc_title"] == "Andrés Felipe Rojas Martínez — Hoja de vida"
    assert [link["display"] for link in ctx["links"]] == [
        "linkedin.com/in/andres-rojas-dev",
        "github.com/andresrojas-dev",
    ]
    assert ctx["lang"] == "es" and ctx["destination"] == "ats" and ctx["for_preview"] is False


def test_sections_titles_ats_upper_mail_title(session: Session, seeded: int) -> None:
    ats = _ctx(session, seeded, Destination.ATS)
    mail = _ctx(session, seeded, Destination.MAIL)
    assert [s["title"] for s in ats["sections"]] == [
        "RESUMEN PROFESIONAL",
        "EXPERIENCIA PROFESIONAL",
        "EDUCACIÓN",
        "HABILIDADES",
        "PROYECTOS",
        "CERTIFICACIONES",
        "IDIOMAS",
    ]
    assert mail["sections_by_key"]["experience"]["title"] == "Experiencia profesional"
    assert ats["sections"][0]["entries"] == []  # summary uses basics.summary


def test_english_titles_and_dates(session: Session, seeded: int) -> None:
    ResumeService(session).update(seeded, ResumeUpdate(language="en"))
    ats = _ctx(session, seeded, Destination.ATS)
    mail = _ctx(session, seeded, Destination.MAIL)
    assert [s["title"] for s in ats["sections"]][:3] == ["SUMMARY", "EXPERIENCE", "EDUCATION"]
    assert ats["t"]["present"] == "Present"
    current = ats["sections_by_key"]["experience"]["entries"][0]
    assert current["dates"] == "03/2022 – Present"
    assert current["location"] == "Bogotá · Remote"
    assert current["employment_type_label"] == "Full-time"
    # "Correo" profile uses MMM YYYY
    assert mail["sections_by_key"]["experience"]["entries"][0]["dates"] == "Mar 2022 – Present"
    assert ats["basics"]["location"] == "Bogotá, Cundinamarca, Colombia"
    assert ats["doc_title"].endswith("— Resume")
    skill = ats["sections_by_key"]["skills"]["entries"][0]["skills"][0]
    assert (skill["level_label"], skill["years_label"]) == ("Expert", "8 years")


def test_spanish_dates_and_labels(session: Session, seeded: int) -> None:
    ats = _ctx(session, seeded, Destination.ATS)
    mail = _ctx(session, seeded, Destination.MAIL)
    exps = ats["sections_by_key"]["experience"]["entries"]
    assert [e["dates"] for e in exps] == [
        "03/2022 – Actual",
        "06/2019 – 02/2022",
        "01/2017 – 05/2019",
    ]
    assert exps[0]["location"] == "Bogotá · Remoto"
    assert exps[1]["location"] == "Bogotá, Colombia"
    assert exps[2]["employment_type_label"] == "Contratista"
    assert mail["sections_by_key"]["experience"]["entries"][1]["dates"] == "jun 2019 – feb 2022"
    skills = ats["sections_by_key"]["skills"]["entries"]
    assert skills[0]["names"] == "Python, Go, SQL, TypeScript"
    assert skills[0]["skills"][0]["level_label"] == "Experto"
    assert skills[0]["skills"][0]["years_label"] == "8 años"
    langs = ats["sections_by_key"]["languages"]["entries"]
    assert [x["level_label"] for x in langs] == ["Nativo", "C1 — Avanzado"]
    cert = ats["sections_by_key"]["certifications"]["entries"][0]
    assert (cert["date"], cert["expiry"]) == ("05/2024", "05/2027")


def test_education_in_progress_dates(session: Session, seeded: int) -> None:
    edu = EducationService(session).list(seeded)[0]
    EducationService(session).update(edu.id, EducationUpdate(in_progress=True, end_date=None))
    ctx = _ctx(session, seeded, Destination.ATS)
    first = ctx["sections_by_key"]["education"]["entries"][0]
    assert first["dates"] == "02/2020 – En curso"
    assert first["in_progress"] is True


def test_show_in_filter(session: Session, seeded: int) -> None:
    exps = ExperienceService(session)
    first, second = exps.list(seeded)[:2]
    ach = first.achievements[0]
    exps.achievements.update(ach.id, AchievementUpdate(show_in=ShowIn.MAIL))
    exps.update(second.id, ExperienceUpdate(show_in=ShowIn.ATS))

    ats = _ctx(session, seeded, Destination.ATS)["sections_by_key"]["experience"]["entries"]
    mail = _ctx(session, seeded, Destination.MAIL)["sections_by_key"]["experience"]["entries"]
    assert ach.text not in ats[0]["achievements"]
    assert ach.text in mail[0]["achievements"]
    assert second.id in [e["id"] for e in ats]
    assert second.id not in [e["id"] for e in mail]


def test_section_order_visibility_and_override(session: Session, seeded: int) -> None:
    cv = _cv(session, seeded)
    ats_profile = _profile(cv, Destination.ATS)
    order = [
        SectionKey.EXPERIENCE,
        SectionKey.SKILLS,
        SectionKey.SUMMARY,
        SectionKey.EDUCATION,
        SectionKey.LANGUAGES,
        SectionKey.CERTIFICATIONS,
        SectionKey.PROJECTS,
    ]
    ProfileService(session).set_sections(
        ats_profile.id,
        [
            ProfileSectionIn(
                section=key,
                visible=key != SectionKey.PROJECTS,
                title_override="Trayectoria" if key == SectionKey.EXPERIENCE else None,
            )
            for key in order
        ],
    )
    ctx = _ctx(session, seeded, Destination.ATS)
    assert [s["key"] for s in ctx["sections"]] == [k.value for k in order[:-1]]
    assert ctx["sections"][0]["title"] == "TRAYECTORIA"
    assert "projects" not in ctx["sections_by_key"]


def test_empty_sections_and_summary_are_skipped(session: Session) -> None:
    from schemas import ResumeCreate

    rid = ResumeService(session).create(ResumeCreate(name="Vacío")).id
    ctx = _ctx(session, rid, Destination.ATS)
    assert ctx["sections"] == []
    assert ctx["basics"]["location"] == "Colombia"
    assert ctx["doc_title"] == "Hoja de vida"


def test_photo_only_in_mail_with_include_photo(
    session: Session, seeded: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "abc_400.jpg").write_bytes(b"\xff\xd8\xff fake jpeg")
    monkeypatch.setenv("CV_ATS_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        asset = AssetOut(
            id=1,
            filename="abc.png",
            original_name="yo.png",
            mime="image/png",
            width=400,
            height=400,
            size_bytes=10,
            sha256="a" * 64,
        )
        cv = _cv(session, seeded)
        cv = cv.model_copy(update={"basics": cv.basics.model_copy(update={"photo": asset})})
        mail = _profile(cv, Destination.MAIL)
        ats = _profile(cv, Destination.ATS)

        assert build_context(cv, mail)["basics"]["photo_src"] is None  # include_photo False
        with_photo = mail.model_copy(update={"include_photo": True})
        src = build_context(cv, with_photo)["basics"]["photo_src"]
        assert src is not None and src.startswith("data:image/jpeg;base64,")
        forced = ats.model_copy(update={"include_photo": True})  # never in ats
        assert build_context(cv, forced)["basics"]["photo_src"] is None
    finally:
        get_settings.cache_clear()


# ------------------------------------------------------------------------ HTML


@pytest.mark.skipif(not HAS_ATS, reason="render/templates/ats/base.html aún no existe")
def test_ats_html_has_no_tables_or_images(session: Session, seeded: int) -> None:
    cv = _cv(session, seeded)
    result = render(cv, _profile(cv, Destination.ATS))
    assert isinstance(result, RenderResult)
    assert result.pages is None
    html = result.html.lower()
    assert "<table" not in html
    assert "<img" not in html
    assert "andrés felipe rojas martínez" in html
    assert "experiencia profesional" in html
    assert "+57 300 123 4567" in html
    assert 'data-entity="experience"' in html


@pytest.mark.skipif(not HAS_ATS, reason="render/templates/ats/base.html aún no existe")
def test_ats_html_escapes_user_content(session: Session, seeded: int) -> None:
    exp = ExperienceService(session).list(seeded)[0]
    ExperienceService(session).update(exp.id, ExperienceUpdate(company="<script>x</script>"))
    cv = _cv(session, seeded)
    html = render(cv, _profile(cv, Destination.ATS)).html
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.skipif(not HAS_MAIL, reason="render/templates/mail/base.html aún no existe")
def test_mail_html_renders_with_preview_flag(session: Session, seeded: int) -> None:
    cv = _cv(session, seeded)
    result = render(cv, _profile(cv, Destination.MAIL), for_preview=True)
    assert "Experiencia profesional" in result.html
    assert "is-preview" in result.html
