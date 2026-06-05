"""Company ORM model.

A Company is the top-level tenant entity in CairnBooks.  Every financial
record (chart of accounts, journal entries, etc.) is scoped to a Company via
the ``tenant_id`` column supplied by :class:`~app.db.mixins.TenantMixin`.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mixins import TenantMixin
from app.db.session import Base


class Company(TenantMixin, Base):
    """Represents a business entity (tenant) using CairnBooks.

    Attributes
    ----------
    id:
        Surrogate primary key (UUID v4), generated on the client side.
    tenant_id:
        UUID of the owning tenant (inherited from :class:`~app.db.mixins.TenantMixin`).
        For a Company row this will typically equal the Company's own ``id``
        once the tenant-provisioning flow is wired up.
    name:
        Human-readable company name (max 255 characters).
    created_at:
        UTC timestamp set automatically by the database on INSERT.
    updated_at:
        UTC timestamp refreshed automatically by the database on UPDATE.
    """

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
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
        return f"<Company id={self.id!r} name={self.name!r}>"
