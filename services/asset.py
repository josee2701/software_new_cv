"""Uploaded photos (spec §4.4 ``asset``): validate, crop, store and dedupe.

The same logic serves ``POST /api/assets`` (spec §6) and ``POST /ui/resumes/{id}/photo``
(contract §4.2): the server always re-validates and re-crops, even when the browser cropped
the image already.
"""

from __future__ import annotations

import hashlib
import io
import logging
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select

from app.config import get_settings
from models import Asset, Basics
from models.asset import MAX_ASSET_BYTES
from services.base import TransactionalService
from services.errors import InvalidDataError, NotFoundError

logger = logging.getLogger(__name__)

#: Pillow format → mime accepted on upload (the CHECK of ``asset.mime``).
INPUT_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
#: Everything is normalized to JPEG (see docs/DECISIONS.md).
STORED_MIME = "image/jpeg"
STORED_EXT = ".jpg"
MAX_SIDE = 800
RENDER_SIDE = 400
RENDER_SUFFIX = "_400.jpg"

TOO_BIG = "La imagen supera el máximo de 5 MB"
BAD_FORMAT = "Formato no admitido: usa JPEG, PNG o WebP"
EMPTY_FILE = "El archivo está vacío"


def _square(image: Image.Image) -> Image.Image:
    """Centred square crop."""
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def _jpeg(image: Image.Image, side: int) -> bytes:
    target = (side, side)
    resized = image if image.size == target else image.resize(target, Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    resized.convert("RGB").save(buffer, format="JPEG", quality=88, optimize=True)
    return buffer.getvalue()


class AssetService(TransactionalService):
    """Creates, reads and deletes ``asset`` rows together with their files on disk."""

    @property
    def uploads_dir(self) -> Path:
        return get_settings().uploads_dir

    # ------------------------------------------------------------------ reads

    def get(self, asset_id: int) -> Asset:
        asset = self.session.get(Asset, asset_id)
        if asset is None:
            raise NotFoundError(f"No existe la foto con id {asset_id}")
        return asset

    def render_path(self, asset: Asset) -> Path:
        """Path of the ``_400.jpg`` version used by the render and by ``GET /ui/assets/{id}``."""
        path = self.uploads_dir / f"{Path(asset.filename).stem}{RENDER_SUFFIX}"
        if not path.is_file():
            original = self.uploads_dir / asset.filename
            if not original.is_file():
                raise NotFoundError("El archivo de la foto no está en el disco")
            return original
        return path

    def find_by_sha256(self, digest: str) -> Asset | None:
        return self.session.scalar(select(Asset).where(Asset.sha256 == digest))

    # ------------------------------------------------------------------ writes

    def create(self, data: bytes, original_name: str) -> Asset:
        """Validate, crop to a centred square, store ``<uuid>.jpg`` + ``<uuid>_400.jpg``.

        Returns the existing row when the normalized image is already stored (sha256 dedupe).
        """
        if not data:
            raise InvalidDataError.single("file", EMPTY_FILE)
        if len(data) > MAX_ASSET_BYTES:
            raise InvalidDataError.single("file", TOO_BIG)
        try:
            with Image.open(io.BytesIO(data)) as opened:
                if (opened.format or "") not in INPUT_FORMATS:
                    raise InvalidDataError.single("file", BAD_FORMAT)
                opened.load()
                square = _square(opened)
                side = min(square.size[0], MAX_SIDE)
                main = _jpeg(square, side)
                thumb = _jpeg(square, RENDER_SIDE)
        except (UnidentifiedImageError, OSError) as exc:
            raise InvalidDataError.single("file", BAD_FORMAT) from exc

        digest = hashlib.sha256(main).hexdigest()
        existing = self.find_by_sha256(digest)
        if existing is not None:
            self._write_files(existing.filename, main, thumb)  # self-heal a missing file
            return existing

        filename = f"{uuid.uuid4().hex}{STORED_EXT}"
        self._write_files(filename, main, thumb)
        with self._write():
            asset = Asset(
                filename=filename,
                original_name=(original_name or filename)[:255],
                mime=STORED_MIME,
                width=side,
                height=side,
                size_bytes=len(main),
                sha256=digest,
            )
            self.session.add(asset)
            self.session.flush()
        return asset

    def _write_files(self, filename: str, main: bytes, thumb: bytes) -> None:
        folder = self.uploads_dir
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_bytes(main)
        (folder / f"{Path(filename).stem}{RENDER_SUFFIX}").write_bytes(thumb)

    def delete(self, asset_id: int) -> None:
        """Delete the row and both files (spec §4.5 rule 3; the FK sets ``photo_asset_id`` NULL)."""
        asset = self.get(asset_id)
        filename = asset.filename
        with self._write():
            self.session.delete(asset)
            self.session.flush()
        self._remove_files(filename)

    def _remove_files(self, filename: str) -> None:
        folder = self.uploads_dir
        for path in (folder / filename, folder / f"{Path(filename).stem}{RENDER_SUFFIX}"):
            try:
                path.unlink(missing_ok=True)
            except OSError:  # pragma: no cover - the row is already gone
                logger.warning("No se pudo borrar %s", path, exc_info=True)

    def delete_if_unused(self, asset_id: int) -> bool:
        """Delete the asset when no ``basics`` points at it any more. True if deleted."""
        used = self.session.scalar(
            select(Basics.id).where(Basics.photo_asset_id == asset_id).limit(1)
        )
        if used is not None:
            return False
        self.delete(asset_id)
        return True
