"""``structure.*`` rules: positive/negative cases and severity per destination."""

from __future__ import annotations

import pytest

from models.enums import SectionKey
from render.renderer import render
from tests.validator_factories import (
    check,
    edu,
    make_ctx,
    make_cv,
    make_profile,
    sections,
    severities,
)
from validator.rules.structure import is_canonical_heading


@pytest.mark.parametrize(
    "css",
    [
        ".a{display:grid}",
        ".a{display: inline-grid}",
        ".a{grid-template-columns: 1fr 2fr}",
        ".a{columns: 2}",
        ".a{column-count:2}",
        ".a{float: left}",
        ".a{position:absolute}",
    ],
)
def test_single_column_detects_layouts(css: str) -> None:
    html = f"<style>{css}</style><p>x</p>"
    assert severities("structure.single_column", make_ctx("ats", html=html)) == {"error"}
    assert check("structure.single_column", make_ctx("mail", html=html)) == []


def test_single_column_ignores_comments_and_missing_html() -> None:
    html = "<style>/* sin position:absolute ni display:grid */ .a{color:#000}</style>"
    assert check("structure.single_column", make_ctx("ats", html=html)) == []
    assert check("structure.single_column", make_ctx("ats", html=None)) == []


def test_real_templates() -> None:
    cv = make_cv()
    ats_html = render(cv, make_profile("ats")).html
    for rule_id in ("structure.single_column", "structure.no_tables", "structure.no_photo"):
        assert check(rule_id, make_ctx("ats", html=ats_html)) == []
    mail_html = render(cv, make_profile("mail")).html
    # The mail template is two-column: only relevant for ats, so a mail html run in ats fails.
    assert check("structure.single_column", make_ctx("ats", html=mail_html)) != []


def test_no_tables() -> None:
    html = "<TABLE><tr><td>x</td></tr></TABLE>"
    assert severities("structure.no_tables", make_ctx("ats", html=html)) == {"error"}
    assert check("structure.no_tables", make_ctx("mail", html=html)) == []
    assert check("structure.no_tables", make_ctx("ats", html="<p>tabla</p>")) == []
    assert check("structure.no_tables", make_ctx("ats", html=None)) == []


def test_no_photo() -> None:
    profile = make_profile("ats").model_copy(update={"include_photo": True})
    findings = check("structure.no_photo", make_ctx("ats", profile=profile, html="<img src=x>"))
    assert len(findings) == 2 and {f.severity.value for f in findings} == {"error"}
    assert check("structure.no_photo", make_ctx("ats", html="<p>foto</p>")) == []
    assert check("structure.no_photo", make_ctx("mail", html="<img src=x>")) == []


def test_section_order() -> None:
    order = [SectionKey.SUMMARY, SectionKey.SKILLS, SectionKey.EXPERIENCE, SectionKey.EDUCATION]
    profile = make_profile("ats", sections=sections(order))
    (finding,) = check("structure.section_order", make_ctx("ats", profile=profile))
    assert finding.severity.value == "warning"
    assert "habilidades → experiencia" in finding.message
    mail = make_profile("mail", sections=sections(order))
    assert check("structure.section_order", make_ctx("mail", profile=mail)) == []
    # Hidden sections do not count.
    hidden = make_profile("ats", sections=sections(order, skills={"visible": False}))
    assert check("structure.section_order", make_ctx("ats", profile=hidden)) == []
    assert check("structure.section_order", make_ctx("ats")) == []


@pytest.mark.parametrize(
    ("key", "title", "ok"),
    [
        (SectionKey.EXPERIENCE, "Experiencia laboral", True),
        (SectionKey.EXPERIENCE, "WORK EXPERIENCE", True),
        (SectionKey.CERTIFICATIONS, "Licencias & certificaciones", True),
        (SectionKey.CERTIFICATIONS, "Licenses & Certifications", True),
        (SectionKey.EDUCATION, "Formación académica", True),
        (SectionKey.SKILLS, "Mis superpoderes", False),
        (SectionKey.SKILLS, "Experiencia", False),  # valid heading, wrong section
    ],
)
def test_canonical_heading_whitelist(key: SectionKey, title: str, ok: bool) -> None:
    assert is_canonical_heading(key, title) is ok


def test_canonical_headings_rule() -> None:
    bad = make_profile("ats", sections=sections(skills={"title_override": "Lo que sé hacer"}))
    (finding,) = check("structure.canonical_headings", make_ctx("ats", profile=bad))
    assert finding.severity.value == "error"
    assert (finding.entity, finding.entity_id) == ("profile_section", 13)
    bad_mail = make_profile("mail", sections=sections(skills={"title_override": "Lo que sé hacer"}))
    assert check("structure.canonical_headings", make_ctx("mail", profile=bad_mail)) == []
    hidden = make_profile(
        "ats", sections=sections(skills={"title_override": "Otra cosa", "visible": False})
    )
    assert check("structure.canonical_headings", make_ctx("ats", profile=hidden)) == []
    good = make_profile("ats", sections=sections(experience={"title_override": "Trayectoria"}))
    assert check("structure.canonical_headings", make_ctx("ats", profile=good)) != []
    good = make_profile(
        "ats", sections=sections(experience={"title_override": "Trayectoria profesional"})
    )
    assert check("structure.canonical_headings", make_ctx("ats", profile=good)) == []


@pytest.mark.parametrize(("dest", "expected"), [("ats", "error"), ("mail", "warning")])
def test_required_sections(dest: str, expected: str) -> None:
    ctx = make_ctx(dest, cv=make_cv(experiences=[]))
    (finding,) = check("structure.required_sections", ctx)
    assert finding.severity.value == expected and "experiencia" in finding.message
    hidden = make_profile(dest, sections=sections(education={"visible": False}))
    (finding,) = check("structure.required_sections", make_ctx(dest, profile=hidden))
    assert "oculta" in finding.message
    assert check("structure.required_sections", make_ctx(dest)) == []


def test_required_sections_respects_show_in() -> None:
    cv = make_cv(education=[edu(1, show_in="mail")])
    assert check("structure.required_sections", make_ctx("ats", cv=cv)) != []
    assert check("structure.required_sections", make_ctx("mail", cv=cv)) == []
