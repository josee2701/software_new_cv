"""Generic CRUD + ordering for sortable child entities (spec §4.5 rule 1)."""

from __future__ import annotations

import builtins
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.base import Base, OrderedEntity, OrderMixin
from services.errors import ConflictError, InvalidDataError, NotFoundError, validate_model


def apply_order(session: Session, items: Sequence[OrderMixin]) -> None:
    """Rewrite positions to 0..n-1 in the given order without hitting UNIQUE(parent, position).

    SQLite cannot defer UNIQUE constraints, so positions are first moved to distinct negative
    values and then to their final value, inside the caller's transaction.
    """
    for index, item in enumerate(items):
        item.position = -(index + 1)
    session.flush()
    for index, item in enumerate(items):
        item.position = index
    session.flush()


class TransactionalService:
    def __init__(self, session: Session) -> None:
        self.session = session

    @contextmanager
    def _write(self) -> Iterator[None]:
        """Unit of work: commit on success; rollback and map integrity errors to 409."""
        try:
            yield
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                "La operación viola una restricción de integridad de los datos"
            ) from exc
        except Exception:
            self.session.rollback()
            raise


class ChildService[M: OrderedEntity](TransactionalService):
    """CRUD for an ordered child entity of ``parent_model`` linked by ``parent_fk``.

    Updates are merged with the current state and re-validated with ``create_schema`` so the
    cross-field rules (dates, is_current, ...) always hold.
    """

    model: type[M]
    parent_model: type[Base]
    parent_fk: str
    create_schema: type[BaseModel]
    label: str  # "la experiencia"
    parent_label: str  # "el CV"
    unique_fields: tuple[str, ...] = ()
    unique_message: str = "Ya existe un elemento con ese nombre"

    # ------------------------------------------------------------------ reads

    def require_parent(self, parent_id: int) -> None:
        if self.session.get(self.parent_model, parent_id) is None:
            raise NotFoundError(f"No existe {self.parent_label} con id {parent_id}")

    def list(self, parent_id: int) -> list[M]:
        self.require_parent(parent_id)
        stmt = (
            select(self.model)
            .where(getattr(self.model, self.parent_fk) == parent_id)
            .order_by(self.model.position)
        )
        return list(self.session.scalars(stmt))

    def get(self, item_id: int, parent_id: int | None = None) -> M:
        item = self.session.get(self.model, item_id)
        if item is None or (parent_id is not None and self.parent_of(item) != parent_id):
            raise NotFoundError(f"No existe {self.label} con id {item_id}")
        return item

    def parent_of(self, item: M) -> int:
        value: int = getattr(item, self.parent_fk)
        return value

    # ------------------------------------------------------------------ writes

    def create(self, parent_id: int, data: BaseModel) -> M:
        with self._write():
            siblings = self.list(parent_id)
            values = data.model_dump()
            self._check_unique(parent_id, values, exclude_id=None)
            self._check_refs(values)
            item = self.model(**values)
            setattr(item, self.parent_fk, parent_id)
            item.position = len(siblings)
            self.session.add(item)
            self.session.flush()
            self._after_write(item)
        return item

    def update(self, item_id: int, patch: BaseModel, parent_id: int | None = None) -> M:
        with self._write():
            item = self.get(item_id, parent_id)
            changes = self._prepare_update(item, patch.model_dump(exclude_unset=True))
            current = {name: getattr(item, name) for name in self.create_schema.model_fields}
            validated = validate_model(self.create_schema, {**current, **changes})
            values = {name: getattr(validated, name) for name in changes}
            self._check_unique(self.parent_of(item), values, exclude_id=item.id)
            self._check_refs(values)
            for name, value in values.items():
                setattr(item, name, value)
            self.session.flush()
            self._after_write(item)
        return item

    def delete(self, item_id: int, parent_id: int | None = None) -> None:
        with self._write():
            item = self.get(item_id, parent_id)
            owner = self.parent_of(item)
            self.session.delete(item)
            self.session.flush()
            apply_order(self.session, self.list(owner))

    def reorder(self, parent_id: int, ids: Sequence[int]) -> builtins.list[M]:
        with self._write():
            items = self.list(parent_id)
            by_id = {item.id: item for item in items}
            if len(set(ids)) != len(ids) or set(ids) != set(by_id):
                raise InvalidDataError.single(
                    "ids", "La lista debe contener exactamente los ids actuales, sin repetir"
                )
            apply_order(self.session, [by_id[i] for i in ids])
        return self.list(parent_id)

    # ------------------------------------------------------------------ hooks

    def _prepare_update(self, item: M, changes: dict[str, Any]) -> dict[str, Any]:
        return changes

    def _after_write(self, item: M) -> None:
        return None

    def _check_refs(self, values: dict[str, Any]) -> None:
        return None

    def _check_unique(self, parent_id: int, values: dict[str, Any], exclude_id: int | None) -> None:
        for name in self.unique_fields:
            value = values.get(name)
            if not isinstance(value, str):
                continue
            column = getattr(self.model, name)
            stmt = select(self.model.id).where(
                getattr(self.model, self.parent_fk) == parent_id,
                func.lower(column) == value.lower(),
            )
            if exclude_id is not None:
                stmt = stmt.where(self.model.id != exclude_id)
            if self.session.scalar(stmt) is not None:
                raise ConflictError(self.unique_message)
