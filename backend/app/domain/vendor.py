"""Vendor ORM model.

A Vendor represents an external party (supplier, contractor, or service
provider) from whom a Company purchases goods or services.  Every Vendor row
is scoped to a tenant via the ``tenant_id`` column supplied by
:class:`~app.db.mixins.TenantMixin`.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mixins import TenantMixin
from app.db.session import Base


class Vendor(TenantMixin, Base):
    """Represents an external supplier or service provider.

    Attributes
    ----------
    id:
        Surrogate primary key (UUID v4), generated on the client side.
    tenant_id:
        UUID of the owning tenant (inherited from :class:`~app.db.mixins.TenantMixin`).
    name:
        Human-readable vendor name (max 255 characters), required.
    email:
        Primary contact email address (optional).
    phone:
        Primary contact phone number (optional).
    website:
        Vendor website URL (optional).
    address_line1:
        Street address line 1 (optional).
    address_line2:
        Street address line 2, e.g. suite or unit number (optional).
    city:
        City (optional).
    state:
        State, province, or region (optional).
    postal_code:
        Postal / ZIP code (optional).
    country:
        ISO 3166-1 alpha-2 country code or full country name (optional).
    created_at:
        UTC timestamp set automatically by the database on INSERT.
    updated_at:
        UTC timestamp refreshed automatically by the database on UPDATE.
    """

    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    website: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )
    address_line1: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    address_line2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vendor id={self.id!r} name={self.name!r}>"
