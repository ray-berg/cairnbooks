"""Company model — a bookkeeping entity that belongs to a Tenant."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.tenant import Tenant


class Company(Base):
    """A bookkeeping entity (legal entity / business) within a Tenant."""

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    currency: Mapped[str] = mapped_column(
        sa.String(3),
        nullable=False,
        server_default="USD",
    )
    fiscal_year_start_month: Mapped[int] = mapped_column(
        sa.SmallInteger(),
        nullable=False,
        server_default="1",
        comment="ISO month number (1 = January) when the fiscal year begins.",
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    tenant: Mapped[Tenant] = relationship(
        "Tenant",
        back_populates="companies",
    )
    accounts: Mapped[list[Account]] = relationship(
        "Account",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id!s} name={self.name!r} tenant_id={self.tenant_id!s}>"
