"""``contact.*`` rules: positive/negative cases and severity per destination."""

from __future__ import annotations

import pytest

from tests.validator_factories import check, make_ctx, make_cv, severities
from validator.rules.contact import phone_digits

LINK = "https://www.linkedin.com/in/ana-gomez"


@pytest.mark.parametrize("email", ["", "   ", "no-es-un-correo"])
@pytest.mark.parametrize(("dest", "expected"), [("ats", "error"), ("mail", "error")])
def test_email_present(email: str, dest: str, expected: str) -> None:
    assert severities("contact.email_present", make_ctx(dest, cv=make_cv({"email": email}))) == {
        expected
    }
    assert check("contact.email_present", make_ctx(dest)) == []


@pytest.mark.parametrize("phone", ["", "300 123 4567", "+57"])
@pytest.mark.parametrize(("dest", "expected"), [("ats", "error"), ("mail", "warning")])
def test_phone_present(phone: str, dest: str, expected: str) -> None:
    assert severities("contact.phone_present", make_ctx(dest, cv=make_cv({"phone": phone}))) == {
        expected
    }
    assert check("contact.phone_present", make_ctx(dest)) == []


def test_phone_digits() -> None:
    assert phone_digits("+57 300-123 4567") == "573001234567"
    assert phone_digits("") == ""


@pytest.mark.parametrize(("dest", "expected"), [("ats", "warning"), ("mail", "info")])
def test_location_present(dest: str, expected: str) -> None:
    ctx = make_ctx(dest, cv=make_cv({"city": "", "country": ""}))
    (finding,) = check("contact.location_present", ctx)
    assert finding.severity.value == expected
    assert "ciudad y país" in finding.message
    assert check("contact.location_present", make_ctx(dest)) == []


@pytest.mark.parametrize(("dest", "expected"), [("ats", "warning"), ("mail", "info")])
def test_linkedin_present(dest: str, expected: str) -> None:
    github = {
        "id": 2,
        "kind": "github",
        "label": None,
        "url": "https://github.com/a",
        "position": 0,
    }
    assert severities("contact.linkedin_present", make_ctx(dest, cv=make_cv(links=[github]))) == {
        expected
    }
    assert check("contact.linkedin_present", make_ctx(dest)) == []


def test_url_plain_ats_only_and_needs_html() -> None:
    bad = f'<p><a href="{LINK}">aquí</a> <a href="mailto:a@b.co">escríbeme</a></p>'
    (finding,) = check("contact.url_plain", make_ctx("ats", html=bad))
    assert finding.severity.value == "error"
    assert (finding.entity, finding.entity_id) == ("contact_link", 1)
    assert check("contact.url_plain", make_ctx("mail", html=bad)) == []
    assert check("contact.url_plain", make_ctx("ats", html=None)) == []
    good = f'<a href="{LINK}">linkedin.com/in/ana-gomez</a>'
    assert check("contact.url_plain", make_ctx("ats", html=good)) == []
    unknown = '<a href="https://example.org/x"></a>'
    (finding,) = check("contact.url_plain", make_ctx("ats", html=unknown))
    assert finding.entity is None and "(vacío)" in finding.message
