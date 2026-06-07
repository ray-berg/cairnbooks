"""Item (Product/Service) CRUD API.

Endpoints
---------
POST   /companies/{company_id}/items              Create a new item.
GET    /companies/{company_id}/items              List items for a company.
GET    /companies/{company_id}/items/{item_id}    Retrieve a single item.
PATCH  /companies/{company_id}/items/{item_id}    Partially update an item.
DELETE /companies/{company_id}/items/{item_id}    Delete an item.

All endpoints are scoped to a specific company so that item data from different
companies remains fully isolated.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cairnbooks.db import get_db
from cairnbooks.models.item import Item

router = APIRouter(
    prefix="/companies/{company_id}/items",
    tags=["items"],
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ItemCreate(BaseModel):
    """Request body for creating a new item."""

    name: str = Field(..., min_length=1, max_length=255, description="Product or service name.")
    description: str | None = Field(None, description="Optional longer description.")
    income_account_id: uuid.UUID | None = Field(
        None,
        description="Revenue account to credit when this item is sold on an invoice.",
    )
    expense_account_id: uuid.UUID | None = Field(
        None,
        description="Cost/expense account to debit when this item appears on a bill.",
    )
    active: bool = Field(True, description="Whether the item is active (visible for use).")


class ItemUpdate(BaseModel):
    """Request body for partially updating an item (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    income_account_id: uuid.UUID | None = None
    expense_account_id: uuid.UUID | None = None
    active: bool | None = None


class ItemResponse(BaseModel):
    """Response schema for a single item."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    description: str | None
    income_account_id: uuid.UUID | None
    expense_account_id: uuid.UUID | None
    active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    company_id: uuid.UUID,
    body: ItemCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Item:
    """Create a new item for the given company.

    Returns the created item with its generated ``id`` and audit timestamps.
    """
    item = Item(
        company_id=company_id,
        name=body.name,
        description=body.description,
        income_account_id=body.income_account_id,
        expense_account_id=body.expense_account_id,
        active=body.active,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.get("", response_model=list[ItemResponse])
async def list_items(
    company_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: Annotated[
        bool,
        Query(description="When true, return only active (non-archived) items."),
    ] = False,
) -> list[Item]:
    """Return all items belonging to *company_id*, ordered by name.

    Pass ``active_only=true`` to filter out archived items.
    """
    stmt = select(Item).where(Item.company_id == company_id).order_by(Item.name)
    if active_only:
        stmt = stmt.where(Item.active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    company_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Item:
    """Retrieve a single item by ``item_id`` within the given company.

    Raises **404** if the item does not exist or belongs to a different company.
    """
    result = await db.execute(
        select(Item).where(Item.id == item_id, Item.company_id == company_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found.",
        )
    return item


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    company_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ItemUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Item:
    """Partially update an item.

    Only the fields provided in the request body are updated; all other fields
    remain unchanged.

    Raises **404** if the item does not exist or belongs to a different company.
    """
    result = await db.execute(
        select(Item).where(Item.id == item_id, Item.company_id == company_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found.",
        )

    patch = body.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(item, field, value)

    await db.flush()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    company_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Permanently delete an item.

    Raises **404** if the item does not exist or belongs to a different company.

    .. note::
        To archive an item without losing history, use the :http:patch:`PATCH`
        endpoint to set ``active=false`` instead.
    """
    result = await db.execute(
        select(Item).where(Item.id == item_id, Item.company_id == company_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found.",
        )
    await db.delete(item)
