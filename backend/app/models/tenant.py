"""Tenant model — top-level organisational unit in the multi-tenant hierarchy."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.company import Company


class Tenant(Base):
    """A SaaS tenant / account that owns one or more Companies."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    slug: Mapped[str] = mapped_column(sa.String(100), unique=True, nullable=False)
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
    companies: Mapped[list[Company]] = relationship(
        "Company",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Tenant id={self.id!s} slug={self.slug!r}>"
