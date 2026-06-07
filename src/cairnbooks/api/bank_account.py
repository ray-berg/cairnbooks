"""CRUD API endpoints for BankAccount.

Routes
------
POST   /bank-accounts                   Create a new bank account
GET    /bank-accounts                   List bank accounts (optional filter: company_id, active_only)
GET    /bank-accounts/{bank_account_id} Retrieve a single bank account by ID
PATCH  /bank-accounts/{bank_account_id} Partially update a bank account
DELETE /bank-accounts/{bank_account_id} Delete a bank account

All routes are async and use the SQLAlchemy AsyncSession from :func:`get_db`.
The session is committed automatically by :func:`get_db` on clean exit and
rolled back on any exception.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cairnbooks.db import get_db
from cairnbooks.models.bank_account import BankAccount

router = APIRouter(prefix="/bank-accounts", tags=["bank-accounts"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class BankAccountCreate(BaseModel):
    """Request body for creating a new bank account."""

    company_id: uuid.UUID
    gl_account_id: uuid.UUID
    name: str
    account_number: str | None = None
    routing_number: str | None = None
    bank_name: str | None = None
    currency: str = "USD"
    active: bool = True


class BankAccountUpdate(BaseModel):
    """Request body for a partial update — every field is optional."""

    gl_account_id: uuid.UUID | None = None
    name: str | None = None
    account_number: str | None = None
    routing_number: str | None = None
    bank_name: str | None = None
    currency: str | None = None
    active: bool | None = None


class BankAccountRead(BaseModel):
    """Response schema for a bank account."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    gl_account_id: uuid.UUID
    name: str
    account_number: str | None = None
    routing_number: str | None = None
    bank_name: str | None = None
    currency: str
    active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_or_404(db: AsyncSession, bank_account_id: uuid.UUID) -> BankAccount:
    """Fetch a BankAccount by id or raise HTTP 404."""
    result = await db.execute(
        select(BankAccount).where(BankAccount.id == bank_account_id)
    )
    bank_account = result.scalar_one_or_none()
    if bank_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BankAccount {bank_account_id} not found.",
        )
    return bank_account


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=BankAccountRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a bank account",
)
async def create_bank_account(
    payload: BankAccountCreate,
    db: AsyncSession = Depends(get_db),
) -> BankAccount:
    """Create a new bank account linked to a GL account."""
    bank_account = BankAccount(
        company_id=payload.company_id,
        gl_account_id=payload.gl_account_id,
        name=payload.name,
        account_number=payload.account_number,
        routing_number=payload.routing_number,
        bank_name=payload.bank_name,
        currency=payload.currency,
        active=payload.active,
    )
    db.add(bank_account)
    await db.flush()
    await db.refresh(bank_account)
    return bank_account


@router.get(
    "",
    response_model=list[BankAccountRead],
    summary="List bank accounts",
)
async def list_bank_accounts(
    company_id: uuid.UUID | None = Query(default=None, description="Filter by company"),
    active_only: bool = Query(default=False, description="Return only active accounts"),
    db: AsyncSession = Depends(get_db),
) -> Sequence[BankAccount]:
    """Return bank accounts, optionally filtered by company and/or active status."""
    stmt = select(BankAccount)
    if company_id is not None:
        stmt = stmt.where(BankAccount.company_id == company_id)
    if active_only:
        stmt = stmt.where(BankAccount.active.is_(True))
    stmt = stmt.order_by(BankAccount.name)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/{bank_account_id}",
    response_model=BankAccountRead,
    summary="Get a bank account by ID",
)
async def get_bank_account(
    bank_account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BankAccount:
    """Retrieve a single bank account by its UUID."""
    return await _get_or_404(db, bank_account_id)


@router.patch(
    "/{bank_account_id}",
    response_model=BankAccountRead,
    summary="Update a bank account",
)
async def update_bank_account(
    bank_account_id: uuid.UUID,
    payload: BankAccountUpdate,
    db: AsyncSession = Depends(get_db),
) -> BankAccount:
    """Partially update a bank account.  Only supplied fields are changed."""
    bank_account = await _get_or_404(db, bank_account_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(bank_account, field, value)
    await db.flush()
    await db.refresh(bank_account)
    return bank_account


@router.delete(
    "/{bank_account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a bank account",
)
async def delete_bank_account(
    bank_account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently delete a bank account.

    To preserve history, consider setting ``active = false`` via PATCH
    instead of deleting the record.
    """
    bank_account = await _get_or_404(db, bank_account_id)
    await db.delete(bank_account)
    await db.flush()
