"""``dates.*`` and ``length.*`` rules: positive/negative cases and severity per destination."""

from __future__ import annotations

import pytest

from tests.validator_factories import (
    GOOD_PDF,
    ach,
    check,
    edu,
    exp,
    make_ctx,
    make_cv,
    make_profile,
    sections,
    severities,
)
from validator.rules.length import visible_text

FUTURE = "2999-01-01"


# ------------------------------------------------------------------ dates


@pytest.mark.parametrize(("dest", "expected"), [("ats", "error"), ("mail", "warning")])
def test_format_consistent_in_text(dest: str, expected: str) -> None:
    text = "Lideré desde ene 2020 la migración de 3 servicios críticos a la nube."
    cv = make_cv(experiences=[exp(1, achievements=[ach(1, text), ach(2, text)])])
    findings = check("dates.format_consistent", make_ctx(dest, cv=cv))
    assert {f.severity.value for f in findings} == {expected}
    assert (findings[0].entity, findings[0].entity_id) == ("achievement", 1)
    assert check("dates.format_consistent", make_ctx(dest)) == []


def test_format_consistent_other_formats_and_html() -> None:
    text = "Lideré en 03/2020 la migración de 3 servicios críticos a la nube."
    cv = make_cv(experiences=[exp(1, achievements=[ach(1, text), ach(2, text)])])
    mmm = make_profile("mail", date_format="MMM YYYY")
    assert check("dates.format_consistent", make_ctx("mail", cv=cv, profile=mmm)) != []
    assert check("dates.format_consistent", make_ctx("ats", cv=cv)) == []  # same format
    html = "<p>03/2020 – Actual</p><p>Vence: may 2027</p>"
    (finding,) = check("dates.format_consistent", make_ctx("ats", html=html))
    assert "may 2027" in finding.message
    bad = make_profile("ats").model_copy(update={"date_format": "DD-MM"})
    (finding,) = check("dates.format_consistent", make_ctx("ats", profile=bad))
    assert finding.entity == "profile"


def test_format_consistent_ignores_bare_years_and_numbers() -> None:
    text = "Reduje 35% el costo en 2021 y atendí 12/15 casos semanales del equipo."
    cv = make_cv(experiences=[exp(1, achievements=[ach(1, text), ach(2, text)])])
    assert check("dates.format_consistent", make_ctx("ats", cv=cv)) == []


@pytest.mark.parametrize(("dest", "expected"), [("ats", "warning"), ("mail", "info")])
def test_chronological(dest: str, expected: str) -> None:
    cv = make_cv(
        experiences=[
            exp(2, position=0),
            exp(1, start_date="2022-01-01", end_date=None, is_current=True, position=1),
        ]
    )
    (finding,) = check("dates.chronological", make_ctx(dest, cv=cv))
    assert finding.severity.value == expected and finding.entity_id == 1
    assert check("dates.chronological", make_ctx(dest)) == []


def test_gap_ats_info_only() -> None:
    cv = make_cv(
        experiences=[
            exp(1, start_date="2023-01-01", end_date=None, is_current=True, position=0),
            exp(2, position=1),  # ends 2021-12
        ]
    )
    (finding,) = check("dates.gap", make_ctx("ats", cv=cv))
    assert finding.severity.value == "info" and "13 meses" in finding.message
    assert check("dates.gap", make_ctx("mail", cv=cv)) == []
    assert check("dates.gap", make_ctx("ats")) == []


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_overlap_current(dest: str) -> None:
    current = {"end_date": None, "is_current": True}
    cv = make_cv(experiences=[exp(1, **current), exp(2, **current)])
    assert severities("dates.overlap_current", make_ctx(dest, cv=cv)) == {"warning"}
    assert check("dates.overlap_current", make_ctx(dest)) == []


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_future(dest: str) -> None:
    cv = make_cv(
        experiences=[exp(1, start_date=FUTURE, end_date=None, is_current=True)],
        education=[edu(1, end_date=FUTURE)],
        projects=[
            {
                "id": 1,
                "name": "P",
                "role": None,
                "description": "d",
                "url": None,
                "start_date": FUTURE,
                "end_date": None,
                "show_in": "both",
                "position": 0,
            }
        ],
    )
    findings = check("dates.future", make_ctx(dest, cv=cv))
    assert [f.entity for f in findings] == ["experience", "education", "project"]
    assert {f.severity.value for f in findings} == {"error"}
    assert check("dates.future", make_ctx(dest)) == []


def test_future_exemptions() -> None:
    cert = {
        "id": 1,
        "name": "AWS",
        "issuer": "Amazon",
        "issue_date": "2024-01-01",
        "expiry_date": FUTURE,
        "credential_id": None,
        "url": None,
        "show_in": "both",
        "position": 0,
    }
    cv = make_cv(education=[edu(1, end_date=FUTURE, in_progress=True)], certifications=[cert])
    assert check("dates.future", make_ctx("ats", cv=cv)) == []


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_end_before_start(dest: str) -> None:
    cert = {
        "id": 3,
        "name": "AWS",
        "issuer": "Amazon",
        "issue_date": "2024-01-01",
        "expiry_date": "2023-01-01",
        "credential_id": None,
        "url": None,
        "show_in": "both",
        "position": 0,
    }
    cv = make_cv(
        experiences=[exp(1, start_date="2020-01-01", end_date="2019-01-01")],
        education=[edu(2, start_date="2020-01-01", end_date="2019-01-01", in_progress=True)],
        certifications=[cert],
    )
    findings = check("dates.end_before_start", make_ctx(dest, cv=cv))
    assert sorted(f.entity or "" for f in findings) == ["certification", "education", "experience"]
    assert {f.severity.value for f in findings} == {"error"}
    assert check("dates.end_before_start", make_ctx(dest)) == []


# ------------------------------------------------------------------ length


@pytest.mark.parametrize(("dest", "expected"), [("ats", "error"), ("mail", "warning")])
def test_pages(dest: str, expected: str) -> None:
    (finding,) = check("length.pages", make_ctx(dest, pages=3))
    assert finding.severity.value == expected and "3 páginas" in finding.message
    assert check("length.pages", make_ctx(dest, pages=2)) == []
    assert check("length.pages", make_ctx(dest, pages=None)) == []
    one = make_profile(dest, max_pages=1)
    assert check("length.pages", make_ctx(dest, profile=one, pages=2)) != []


def test_pages_falls_back_to_pdf_page_count() -> None:
    pdf = GOOD_PDF.__class__(**{**GOOD_PDF.__dict__, "pages": 4})
    assert check("length.pages", make_ctx("ats", pages=None, pdf=pdf)) != []


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_min_content(dest: str) -> None:
    tiny = make_cv(
        {"summary": "Breve."},
        experiences=[exp(1, achievements=[ach(1, "Lideré x.")], technologies=[])],
        skill_categories=[],
        languages=[],
    )
    for pages in (1, None):
        (finding,) = check("length.min_content", make_ctx(dest, cv=tiny, pages=pages))
        assert finding.severity.value == "warning" and "%" in finding.message
    assert check("length.min_content", make_ctx(dest, cv=tiny, pages=2)) == []
    big = make_ctx(dest, cv=tiny, pages=1, html="<p>" + "palabra " * 300 + "</p>")
    assert check("length.min_content", big) == []


def test_visible_text_from_data_respects_sections() -> None:
    cert = {
        "id": 1,
        "name": "CKAD",
        "issuer": "CNCF",
        "issue_date": None,
        "expiry_date": None,
        "credential_id": "X1",
        "url": None,
        "show_in": "both",
        "position": 0,
    }
    project = {
        "id": 1,
        "name": "Sandbox",
        "role": None,
        "description": "Simulador",
        "url": None,
        "start_date": None,
        "end_date": None,
        "show_in": "both",
        "position": 0,
        "technologies": ["Go"],
    }
    cv = make_cv(certifications=[cert], projects=[project])
    text = visible_text(make_ctx("ats", cv=cv))
    assert "CKAD" in text and "Sandbox" in text and "Inglés C1" in text
    hidden = make_profile("ats", sections=sections(projects={"visible": False}))
    assert "Sandbox" not in visible_text(make_ctx("ats", cv=cv, profile=hidden))
