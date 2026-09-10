"""Round-trip verification (spec §9.3, §14)."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

from export.pdf import html_to_pdf
from export.verify import cv_tokens, non_latin1, normalize, tokenize, verify
from models.enums import Destination, ShowIn
from render.renderer import render
from schemas import AchievementUpdate
from services import ExperienceService, ResumeService
from tests._export_helpers import profile_of, seeded_cv


def _pdf(session: Session, destination: Destination) -> tuple[bytes, object, object]:
    cv = seeded_cv(session)
    profile = profile_of(cv, destination)
    result = html_to_pdf(render(cv, profile).html, title="T", author="A")
    return result.data, cv, profile


def test_normalize_and_tokenize() -> None:
    assert normalize("  Ingeniería,  QA/Diseño! ") == "ingenieria qa diseno"
    assert tokenize("Lideré a 4 personas: 99,98%") == {"lidere", "personas", "99", "98"}
    assert non_latin1("abc•–—·ñé€漢 ") == ("€", "漢")


def test_seed_ats_pdf_roundtrip(session: Session) -> None:
    cv = seeded_cv(session)
    profile = profile_of(cv, Destination.ATS)
    data = html_to_pdf(render(cv, profile).html, title="Título", author="Autor").data
    info = verify(data, cv, filename="Andres_Rojas_CV_ats.pdf", profile=profile)
    assert info.has_text
    assert info.coverage >= 0.95, info.missing_tokens
    assert info.email_found and info.phone_found
    assert info.fonts and info.fonts_embedded
    assert info.non_latin1_chars == ()
    assert (info.title, info.author) == ("Título", "Autor")
    assert info.filename == "Andres_Rojas_CV_ats.pdf"
    assert 1 <= info.pages <= 2


def test_seed_mail_pdf_roundtrip(session: Session) -> None:
    cv = seeded_cv(session)
    profile = profile_of(cv, Destination.MAIL)
    data = html_to_pdf(render(cv, profile).html, title="T", author="A").data
    info = verify(data, cv, profile=profile)
    assert info.coverage >= 0.95, info.missing_tokens
    assert info.email_found and info.phone_found


def test_rasterized_pdf_is_detected(session: Session) -> None:
    cv = seeded_cv(session)
    image = Image.new("RGB", (1275, 1650), "white")
    draw = ImageDraw.Draw(image)
    y = 60
    for line in [cv.basics.full_name, cv.basics.email, cv.basics.phone, "EXPERIENCIA"]:
        draw.text((80, y), line, fill="black")
        y += 40
    buffer = io.BytesIO()
    image.save(buffer, format="PDF", resolution=150)
    info = verify(buffer.getvalue(), cv)
    assert info.has_text is False
    assert info.coverage == 0.0
    assert info.fonts == ()
    assert not info.email_found and not info.phone_found
    assert len(info.missing_tokens) == 20


def test_tokens_follow_show_in_and_visible_sections(session: Session) -> None:
    cv = seeded_cv(session)
    exp_service = ExperienceService(session)
    achievement = exp_service.list(cv.id)[0].achievements[0]
    exp_service.achievements.update(achievement.id, AchievementUpdate(show_in=ShowIn.MAIL))
    cv = ResumeService(session).get_out(cv.id)
    ats, mail = profile_of(cv, Destination.ATS), profile_of(cv, Destination.MAIL)
    only_in_mail = tokenize(achievement.text) - cv_tokens(cv, ats)
    assert only_in_mail and only_in_mail <= cv_tokens(cv, mail)
    assert cv_tokens(cv) >= cv_tokens(cv, mail)  # no profile: everything

    hidden = ats.model_copy(
        update={
            "sections": [
                s.model_copy(update={"visible": s.section.value != "skills"}) for s in ats.sections
            ]
        }
    )
    assert "kubernetes" not in cv_tokens(cv, hidden) - tokenize(
        " ".join(a.text for e in cv.experiences for a in e.achievements)
    )
