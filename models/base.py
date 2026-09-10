"""Declarative base, naming convention and mixins (spec §4.2)."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Integer, MetaData, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, sort_order=-100)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), sort_order=100
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        sort_order=101,
    )


class OrderMixin:
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), sort_order=50
    )


class OrderedEntity(IdMixin, TimestampMixin, OrderMixin, Base):
    """Abstract base for sortable child entities with a surrogate id."""

    __abstract__ = True


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def str_enum(enum_cls: type[StrEnum], length: int) -> SAEnum:
    """Python ``StrEnum`` stored as ``VARCHAR(length)`` with a ``CHECK`` on its values."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=length,
        name=_snake(enum_cls.__name__),
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


def table_args(*items: Any) -> tuple[Any, ...]:
    """``__table_args__`` with ``AUTOINCREMENT`` on the SQLite integer PK."""
    return (*items, {"sqlite_autoincrement": True})
