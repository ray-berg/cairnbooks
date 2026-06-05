"""Customer service — CRUD use-cases.

This module owns all Customer lifecycle operations:

- :func:`create_customer` — persist a new customer record.
- :func:`get_customer` — fetch a single customer by id.
- :func:`list_customers` — list customers for a company (active-only by default).
- :func:`update_customer` — partial-update mutable fields.
- :func:`deactivate_customer` — soft-delete by setting ``is_active = False``.

Design notes
------------
- **Tenant isolation**: every function filters on ``tenant_id`` so that
  cross-tenant data leaks are structurally impossible at the service layer.
- **Soft-delete**: :func:`deactivate_customer` sets ``is_active = False``
  rather than issuing a ``DELETE``, preserving referential integrity for
  historical transactions.
- **Partial updates**: :func:`update_customer` only writes fields whose
  keyword argument was explicitly supplied (non-``None``), enabling true
  PATCH semantics without sending every field.
- **No commit**: functions call ``flush()`` so the caller (API route handler
  or test) controls the transaction boundary.
"""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.customer import Customer


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def create_customer(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    name: str,
    email: str | None = None,
    phone: str | None = None,
) -> Customer:
    """Persist a new Customer and return the saved instance.

    Parameters
    ----------
    db:
        Active async database session.
    tenant_id:
        UUID of the owning tenant — used for all subsequent scoped queries.
    company_id:
        UUID of the Company this customer belongs to.
    name:
        Required display name (max 255 chars).
    email:
        Optional contact e-mail address.
    phone:
        Optional contact phone number.
    """
    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        company_id=company_id,
        name=name,
        email=email,
        phone=phone,
        is_active=True,
    )
    db.add(customer)
    await db.flush()
    return customer


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


async def get_customer(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
) -> Customer | None:
    """Return a single Customer scoped to *tenant_id*, or ``None``.

    Returns ``None`` when the record does not exist **or** when it belongs to
    a different tenant (intentionally indistinguishable to callers).
    """
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def list_customers(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    include_inactive: bool = False,
) -> Sequence[Customer]:
    """Return all Customers for the given company, ordered newest-first.

    Parameters
    ----------
    include_inactive:
        When ``False`` (default) only rows where ``is_active = True`` are
        returned.  Pass ``True`` to include deactivated customers (e.g. for
        an admin view).
    """
    stmt = select(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.company_id == company_id,
    )
    if not include_inactive:
        stmt = stmt.where(Customer.is_active.is_(True))
    stmt = stmt.order_by(Customer.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


async def update_customer(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> Customer | None:
    """Partial-update mutable fields of an existing Customer.

    Only keyword arguments that are **not** ``None`` are written.  This
    supports true PATCH semantics: the caller supplies only the fields it
    wants to change.

    Returns the updated Customer instance, or ``None`` if the record was not
    found (or belongs to a different tenant).
    """
    customer = await get_customer(db, tenant_id=tenant_id, customer_id=customer_id)
    if customer is None:
        return None

    if name is not None:
        customer.name = name
    if email is not None:
        customer.email = email
    if phone is not None:
        customer.phone = phone

    db.add(customer)
    await db.flush()
    return customer


# ---------------------------------------------------------------------------
# Deactivate (soft-delete)
# ---------------------------------------------------------------------------


async def deactivate_customer(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
) -> Customer | None:
    """Soft-delete a Customer by setting ``is_active = False``.

    The row is never physically removed, preserving referential integrity for
    historical invoices and transactions.

    This operation is **idempotent**: calling it on an already-inactive
    customer returns the unchanged record without error.

    Returns the Customer instance, or ``None`` if not found.
    """
    customer = await get_customer(db, tenant_id=tenant_id, customer_id=customer_id)
    if customer is None:
        return None

    customer.is_active = False
    db.add(customer)
    await db.flush()
    return customer
