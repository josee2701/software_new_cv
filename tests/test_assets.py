"""Photo uploads: ``services/asset.py``, ``POST /api/assets`` and the editor photo routes."""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session
from app.main import create_app
from models import Asset
from models.asset import MAX_ASSET_BYTES
from services.asset import RENDER_SIDE, RENDER_SUFFIX, AssetService
from services.errors import InvalidDataError, NotFoundError

JPEG = "image/jpeg"


def image_bytes(
    width: int = 1200, height: int = 600, fmt: str = "PNG", color: str = "red"
) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    app = create_app()

    def _session() -> Iterator[Session]:
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def resume_id(client: TestClient) -> int:
    rid: int = client.post("/api/resumes", json={"name": "Con foto"}).json()["id"]
    return rid


# --------------------------------------------------------------------------------- service


def test_create_crops_square_and_writes_both_versions(session: Session) -> None:
    service = AssetService(session)
    asset = service.create(image_bytes(1200, 600), "retrato.png")
    assert asset.width == asset.height == 600  # recorte cuadrado centrado
    assert asset.mime == JPEG and asset.filename.endswith(".jpg")
    assert asset.original_name == "retrato.png"
    assert asset.size_bytes <= MAX_ASSET_BYTES

    folder = service.uploads_dir
    main = folder / asset.filename
    thumb = folder / f"{Path(asset.filename).stem}{RENDER_SUFFIX}"
    assert main.is_file() and thumb.is_file()
    with Image.open(thumb) as img:
        assert img.size == (RENDER_SIDE, RENDER_SIDE)
    assert hashlib.sha256(main.read_bytes()).hexdigest() == asset.sha256
    assert service.render_path(asset) == thumb


def test_create_dedupes_by_sha256(session: Session) -> None:
    service = AssetService(session)
    first = service.create(image_bytes(), "a.png")
    second = service.create(image_bytes(), "b.png")
    assert second.id == first.id
    assert session.query(Asset).count() == 1
    other = service.create(image_bytes(color="blue"), "c.png")
    assert other.id != first.id and session.query(Asset).count() == 2


@pytest.mark.parametrize(
    ("data", "name"),
    [(b"", "x.png"), (b"no soy una imagen", "x.png"), (b"GIF89a" + b"\0" * 20, "x.gif")],
)
def test_create_rejects_invalid_input(session: Session, data: bytes, name: str) -> None:
    with pytest.raises(InvalidDataError):
        AssetService(session).create(data, name)


def test_create_rejects_files_over_5mb(session: Session) -> None:
    with pytest.raises(InvalidDataError):
        AssetService(session).create(b"\0" * (MAX_ASSET_BYTES + 1), "grande.jpg")


def test_delete_removes_row_and_files(session: Session) -> None:
    service = AssetService(session)
    asset = service.create(image_bytes(), "a.png")
    folder, filename = service.uploads_dir, asset.filename
    service.delete(asset.id)
    assert session.get(Asset, asset.id) is None
    assert not (folder / filename).exists()
    assert not (folder / f"{Path(filename).stem}{RENDER_SUFFIX}").exists()
    with pytest.raises(NotFoundError):
        service.get(asset.id)


# ------------------------------------------------------------------------- POST /api/assets


def test_api_upload_asset(client: TestClient) -> None:
    files = {"file": ("foto.png", image_bytes(900, 900), "image/png")}
    r = client.post("/api/assets", files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["mime"] == JPEG and body["width"] == body["height"] == 800  # tope MAX_SIDE
    assert len(body["sha256"]) == 64
    assert client.post("/api/assets", files=files).json()["id"] == body["id"]  # dedupe


def test_api_upload_rejects_non_image(client: TestClient) -> None:
    r = client.post("/api/assets", files={"file": ("x.txt", b"hola", "text/plain")})
    assert r.status_code == 422
    assert r.json()["detail"][0]["field"] == "file"


# ----------------------------------------------------------------- /ui photo (contract §4.2)


def _upload(client: TestClient, resume_id: int, data: bytes | None = None) -> Any:
    files = {"file": ("foto.jpg", data or image_bytes(fmt="JPEG"), JPEG)}
    return client.post(f"/ui/resumes/{resume_id}/photo", files=files)


def test_photo_upload_sets_basics_photo(client: TestClient, resume_id: int) -> None:
    r = _upload(client, resume_id)
    assert r.status_code == 200, r.text
    assert r.headers["hx-trigger"] == "cv-changed"
    assert 'id="sec-basics"' in r.text
    assert "/ui/assets/" in r.text and "Cambiar" in r.text

    basics = client.get(f"/api/resumes/{resume_id}/basics").json()
    asset_id = basics["photo_asset_id"]
    assert asset_id is not None and basics["photo"]["mime"] == JPEG

    photo = client.get(f"/ui/assets/{asset_id}", params={"v": basics["photo"]["sha256"][:8]})
    assert photo.status_code == 200 and photo.headers["content-type"] == JPEG
    with Image.open(io.BytesIO(photo.content)) as img:
        assert img.size == (RENDER_SIDE, RENDER_SIDE)


def test_photo_upload_dedupes(client: TestClient, resume_id: int) -> None:
    same = image_bytes(fmt="JPEG")
    first = _upload(client, resume_id, same)
    assert first.status_code == 200
    asset_id = client.get(f"/api/resumes/{resume_id}/basics").json()["photo_asset_id"]
    assert _upload(client, resume_id, same).status_code == 200
    assert client.get(f"/api/resumes/{resume_id}/basics").json()["photo_asset_id"] == asset_id


def test_photo_replacement_drops_the_unused_asset(client: TestClient, resume_id: int) -> None:
    _upload(client, resume_id, image_bytes(fmt="JPEG"))
    old = client.get(f"/api/resumes/{resume_id}/basics").json()["photo_asset_id"]
    _upload(client, resume_id, image_bytes(fmt="JPEG", color="blue"))
    new = client.get(f"/api/resumes/{resume_id}/basics").json()["photo_asset_id"]
    assert new != old
    assert client.get(f"/ui/assets/{old}").status_code == 404


def test_photo_delete(client: TestClient, resume_id: int) -> None:
    _upload(client, resume_id)
    r = client.delete(f"/ui/resumes/{resume_id}/photo")
    assert r.status_code == 200 and r.headers["hx-trigger"] == "cv-changed"
    assert 'id="sec-basics"' in r.text and "Subir foto" in r.text
    assert client.get(f"/api/resumes/{resume_id}/basics").json()["photo_asset_id"] is None


def test_photo_upload_bad_mime_is_400_plain_text(client: TestClient, resume_id: int) -> None:
    r = client.post(
        f"/ui/resumes/{resume_id}/photo", files={"file": ("x.txt", b"hola", "text/plain")}
    )
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("text/plain")
    assert "JPEG" in r.text


def test_photo_upload_without_file_is_400(client: TestClient, resume_id: int) -> None:
    r = client.post(f"/ui/resumes/{resume_id}/photo", data={"otro": "x"})
    assert r.status_code == 400 and "imagen" in r.text


def test_duplicated_resume_keeps_the_shared_photo(client: TestClient, resume_id: int) -> None:
    """``ResumeService.duplicate`` shares the asset: detaching one must not break the other."""
    _upload(client, resume_id)
    asset_id = client.get(f"/api/resumes/{resume_id}/basics").json()["photo_asset_id"]
    clone = client.post(f"/api/resumes/{resume_id}/duplicate").json()
    assert clone["basics"]["photo_asset_id"] == asset_id

    client.delete(f"/ui/resumes/{resume_id}/photo")
    assert client.get(f"/ui/assets/{asset_id}").status_code == 200  # el clon sigue usándola
    client.delete(f"/ui/resumes/{clone['id']}/photo")
    assert client.get(f"/ui/assets/{asset_id}").status_code == 404
