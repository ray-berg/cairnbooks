"""Customer ORM model.

A Customer represents an individual or business that a Company sells goods or
services to.  Every Customer is scoped to a tenant (via :class:`~app.db.mixins.TenantMixin`)
and belongs to a specific Company.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mixins import TenantMixin
from app.db.session import Base


class Customer(TenantMixin, Base):
    """Represents a customer (buyer) of a Company in CairnBooks.

    Attributes
    ----------
    id:
        Surrogate primary key (UUID v4), generated on the client side.
    tenant_id:
        UUID of the owning tenant (inherited from :class:`~app.db.mixins.TenantMixin`).
    company_id:
        UUID of the :class:`~app.domain.company.Company` that owns this
        customer record.
    name:
        Human-readable customer name (max 255 characters).
    email:
        Optional contact e-mail address (max 254 characters per RFC 5321).
    phone:
        Optional contact phone number (max 50 characters).
    is_active:
        Soft-delete flag.  ``False`` means the customer has been deactivated;
        the row is retained for historical transaction integrity.
    created_at:
        UTC timestamp set automatically by the database on INSERT.
    updated_at:
        UTC timestamp refreshed automatically by the database on UPDATE.
    """

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(
        String(254),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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
        return (
            f"<Customer id={self.id!r} name={self.name!r} active={self.is_active!r}>"
        )
