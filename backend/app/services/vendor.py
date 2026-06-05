"""Vendor service — CRUD use-case orchestration.

All public functions accept an :class:`~sqlalchemy.ext.asyncio.AsyncSession`
as their first argument and a ``tenant_id`` to enforce row-level tenant
isolation.  Transaction boundaries (flush / commit / rollback) are managed
by the caller (typically the FastAPI dependency :func:`~app.db.session.get_db`
which commits on clean exit and rolls back on any exception).

Example::

    from app.db.session import get_db
    from app.services.vendor import create_vendor, list_vendors

    @router.post("/vendors")
    async def post_vendor(payload: VendorCreate, db: AsyncSession = Depends(get_db)):
        vendor = await create_vendor(db, tenant_id=current_tenant_id, name=payload.name)
        return vendor
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.vendor import Vendor


async def create_vendor(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str,
    email: str | None = None,
    phone: str | None = None,
    website: str | None = None,
    address_line1: str | None = None,
    address_line2: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
) -> Vendor:
    """Create and persist a new :class:`~app.domain.vendor.Vendor`.

    Parameters
    ----------
    db:
        Active async database session.
    tenant_id:
        UUID of the owning tenant.
    name:
        Vendor display name (required).
    email, phone, website, address_line1, address_line2, city, state,
    postal_code, country:
        Optional contact and address fields.

    Returns
    -------
    Vendor
        The newly created Vendor instance (flushed but not yet committed).
    """
    vendor = Vendor(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        email=email,
        phone=phone,
        website=website,
        address_line1=address_line1,
        address_line2=address_line2,
        city=city,
        state=state,
        postal_code=postal_code,
        country=country,
    )
    db.add(vendor)
    await db.flush()
    return vendor


async def get_vendor(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    vendor_id: uuid.UUID,
) -> Vendor | None:
    """Fetch a single vendor by primary key, scoped to ``tenant_id``.

    Parameters
    ----------
    db:
        Active async database session.
    tenant_id:
        UUID of the owning tenant.
    vendor_id:
        UUID of the vendor to look up.

    Returns
    -------
    Vendor | None
        The matching :class:`~app.domain.vendor.Vendor`, or ``None`` if not
        found within the tenant.
    """
    stmt = select(Vendor).where(
        Vendor.id == vendor_id,
        Vendor.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_vendors(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> list[Vendor]:
    """Return all vendors belonging to ``tenant_id``, ordered by name.

    Parameters
    ----------
    db:
        Active async database session.
    tenant_id:
        UUID of the owning tenant.

    Returns
    -------
    list[Vendor]
        All vendors for the tenant, sorted alphabetically by ``name``.
    """
    stmt = select(Vendor).where(Vendor.tenant_id == tenant_id).order_by(Vendor.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_vendor(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    vendor_id: uuid.UUID,
    **fields: Any,
) -> Vendor | None:
    """Update mutable fields on an existing vendor.

    Only fields explicitly passed as keyword arguments are modified; omitted
    fields are left unchanged.  Raises :class:`ValueError` if an unknown field
    name is supplied.

    Parameters
    ----------
    db:
        Active async database session.
    tenant_id:
        UUID of the owning tenant.
    vendor_id:
        UUID of the vendor to update.
    **fields:
        Keyword arguments mapping column names to their new values.  Valid
        keys: ``name``, ``email``, ``phone``, ``website``, ``address_line1``,
        ``address_line2``, ``city``, ``state``, ``postal_code``, ``country``.

    Returns
    -------
    Vendor | None
        The updated :class:`~app.domain.vendor.Vendor`, or ``None`` if no
        vendor with that ID exists within the tenant.

    Raises
    ------
    ValueError
        If ``fields`` contains a key that is not a mutable vendor attribute.
    """
    _MUTABLE_FIELDS = frozenset({
        "name", "email", "phone", "website",
        "address_line1", "address_line2",
        "city", "state", "postal_code", "country",
    })
    unknown = set(fields) - _MUTABLE_FIELDS
    if unknown:
        raise ValueError(f"Unknown vendor field(s): {', '.join(sorted(unknown))}")

    vendor = await get_vendor(db, tenant_id=tenant_id, vendor_id=vendor_id)
    if vendor is None:
        return None

    for key, value in fields.items():
        setattr(vendor, key, value)

    await db.flush()
    return vendor


async def delete_vendor(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    vendor_id: uuid.UUID,
) -> bool:
    """Delete a vendor by primary key, scoped to ``tenant_id``.

    Parameters
    ----------
    db:
        Active async database session.
    tenant_id:
        UUID of the owning tenant.
    vendor_id:
        UUID of the vendor to delete.

    Returns
    -------
    bool
        ``True`` if the vendor was found and deleted, ``False`` if no matching
        vendor existed within the tenant.
    """
    vendor = await get_vendor(db, tenant_id=tenant_id, vendor_id=vendor_id)
    if vendor is None:
        return False

    await db.delete(vendor)
    await db.flush()
    return True
