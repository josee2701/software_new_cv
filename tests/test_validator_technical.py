"""``technical.*`` (PdfInfo, POST phase) and ``photo.*`` rules."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from tests.validator_factories import GOOD_PDF, check, make_ctx, make_cv, make_profile
from validator.rules.technical import expected_name_parts


def _pdf(**kw: Any) -> Any:
    return replace(GOOD_PDF, **kw)


def test_technical_rules_need_a_pdf() -> None:
    bad = _pdf(has_text=False, fonts_embedded=False, non_latin1_chars=("★",), author=None)
    assert check("technical.text_extractable", make_ctx("ats", pdf=None)) == []
    assert check("technical.text_extractable", make_ctx("ats", pdf=bad)) != []


@pytest.mark.parametrize(("dest", "expected"), [("ats", "error"), ("mail", "warning")])
def test_text_extractable(dest: str, expected: str) -> None:
    (finding,) = check("technical.text_extractable", make_ctx(dest, pdf=_pdf(has_text=False)))
    assert finding.severity.value == expected and "imagen" in finding.message
    low = _pdf(coverage=0.8, missing_tokens=("kubernetes", "gomez"), email_found=False)
    findings = check("technical.text_extractable", make_ctx(dest, pdf=low))
    assert len(findings) == 2 and "80%" in findings[0].message
    assert "kubernetes, gomez" in findings[0].message
    (finding,) = check("technical.text_extractable", make_ctx(dest, pdf=_pdf(phone_found=False)))
    assert finding.entity == "basics"
    only_low = _pdf(coverage=0.9)
    (finding,) = check("technical.text_extractable", make_ctx(dest, pdf=only_low))
    assert finding.message.endswith("PDF.")
    assert check("technical.text_extractable", make_ctx(dest, pdf=GOOD_PDF)) == []


@pytest.mark.parametrize(("dest", "expected"), [("ats", "error"), ("mail", "info")])
def test_fonts_embedded(dest: str, expected: str) -> None:
    pdf = _pdf(fonts_embedded=False, fonts=("Arial", "Symbol"))
    (finding,) = check("technical.fonts_embedded", make_ctx(dest, pdf=pdf))
    assert finding.severity.value == expected and "Arial, Symbol" in finding.message
    no_names = _pdf(fonts_embedded=False, fonts=())
    assert check("technical.fonts_embedded", make_ctx(dest, pdf=no_names)) != []
    assert check("technical.fonts_embedded", make_ctx(dest, pdf=GOOD_PDF)) == []


def test_no_special_chars_ats_only() -> None:
    pdf = _pdf(non_latin1_chars=("★", "→"))
    (finding,) = check("technical.no_special_chars", make_ctx("ats", pdf=pdf))
    assert finding.severity.value == "warning" and "★ →" in finding.message
    assert check("technical.no_special_chars", make_ctx("mail", pdf=pdf)) == []
    assert check("technical.no_special_chars", make_ctx("ats", pdf=GOOD_PDF)) == []


@pytest.mark.parametrize(
    ("filename", "ok"),
    [
        ("Ana_Gomez_CV_ats.pdf", True),
        ("Ana_Gomez_CV.pdf", True),
        ("Ana_Gomez_CV_correo_sinfoto.docx", True),
        ("ana_gomez_CV_ats.pdf", True),
        ("Ana Gómez CV.pdf", False),
        ("Ana_Gómez_CV.pdf", False),
        ("Ana_CV.pdf", False),
        ("Ana_Gomez_hoja.pdf", False),
        ("Pedro_Perez_CV.pdf", False),
        (None, True),
    ],
)
@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_filename(filename: str | None, ok: bool, dest: str) -> None:
    findings = check("technical.filename", make_ctx(dest, pdf=_pdf(filename=filename)))
    assert (findings == []) is ok
    assert all(f.severity.value == "warning" for f in findings)


def test_expected_name_parts() -> None:
    assert expected_name_parts("Juan de la Cruz Gómez") == ["juan", "cruz", "gomez"]


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_metadata(dest: str) -> None:
    (finding,) = check("technical.metadata", make_ctx(dest, pdf=_pdf(author=None, title="CV")))
    assert finding.severity.value == "info" and "autor y título" in finding.message
    assert check("technical.metadata", make_ctx(dest, pdf=GOOD_PDF)) == []
    nameless = make_cv({"full_name": ""})
    assert check("technical.metadata", make_ctx(dest, cv=nameless, pdf=_pdf(author=None))) == []


# ------------------------------------------------------------------ photo


def test_photo_present_mail() -> None:
    no_photo = make_profile("mail", include_photo=False)
    (finding,) = check("photo.present_mail", make_ctx("mail", profile=no_photo))
    assert finding.severity.value == "info"
    no_asset = make_cv({"photo_asset_id": None})
    assert check("photo.present_mail", make_ctx("mail", cv=no_asset)) != []
    assert check("photo.present_mail", make_ctx("mail")) == []
    assert check("photo.present_mail", make_ctx("ats", cv=no_asset)) == []


@pytest.mark.parametrize("country", ["US", "GB", ""])
def test_photo_warning_region(country: str) -> None:
    cv = make_cv({"country": country})
    (finding,) = check("photo.warning_region", make_ctx("mail", cv=cv))
    assert finding.severity.value == "warning"
    assert check("photo.warning_region", make_ctx("ats", cv=cv)) == []
    no_photo = make_profile("mail", include_photo=False)
    assert check("photo.warning_region", make_ctx("mail", cv=cv, profile=no_photo)) == []


@pytest.mark.parametrize("country", ["CO", "ES", "DE", "FR", "MX"])
def test_photo_region_allowed(country: str) -> None:
    assert check("photo.warning_region", make_ctx("mail", cv=make_cv({"country": country}))) == []
