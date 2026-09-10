"""Router factory for ordered child collections (CRUD + ``PUT .../order``).

Note: no ``from __future__ import annotations`` here: FastAPI must see the real schema
classes in the endpoint signatures built inside the factory.
"""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Body, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import SessionDep
from services.base import ChildService


def register_ordered_crud(
    router: APIRouter,
    *,
    collection: str,
    service: Callable[[Session], ChildService[Any]],
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    out_schema: type[BaseModel],
    name: str,
) -> None:
    """Register list/create/order/get/patch/delete on ``collection`` (``.../{parent_id}/x``)."""
    item = collection + "/{item_id}"

    def _out(obj: Any) -> Any:
        return out_schema.model_validate(obj)

    @router.get(collection, response_model=list[out_schema], name=f"list_{name}")  # type: ignore[valid-type]
    def list_items(parent_id: int, session: SessionDep) -> Any:
        return [_out(x) for x in service(session).list(parent_id)]

    @router.post(
        collection,
        response_model=out_schema,
        status_code=status.HTTP_201_CREATED,
        name=f"create_{name}",
    )
    def create_item(parent_id: int, body: create_schema, session: SessionDep) -> Any:  # type: ignore[valid-type]
        return _out(service(session).create(parent_id, body))

    @router.put(collection + "/order", response_model=list[out_schema], name=f"order_{name}")  # type: ignore[valid-type]
    def order_items(parent_id: int, ids: Annotated[list[int], Body()], session: SessionDep) -> Any:
        return [_out(x) for x in service(session).reorder(parent_id, ids)]

    @router.get(item, response_model=out_schema, name=f"get_{name}")
    def get_item(parent_id: int, item_id: int, session: SessionDep) -> Any:
        return _out(service(session).get(item_id, parent_id))

    @router.patch(item, response_model=out_schema, name=f"update_{name}")
    def update_item(
        parent_id: int,
        item_id: int,
        body: update_schema,  # type: ignore[valid-type]
        session: SessionDep,
    ) -> Any:
        return _out(service(session).update(item_id, body, parent_id))

    @router.delete(item, status_code=status.HTTP_204_NO_CONTENT, name=f"delete_{name}")
    def delete_item(parent_id: int, item_id: int, session: SessionDep) -> Response:
        service(session).delete(item_id, parent_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
