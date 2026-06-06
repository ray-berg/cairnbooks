"""Tenant and Company ORM models.

Multi-tenancy design
--------------------
A **Tenant** is the top-level isolation boundary.  In a SaaS deployment a
Tenant represents one subscribing customer; in a self-hosted deployment
there is typically a single Tenant.

A **Company** is a bookkeeping entity owned by a Tenant.  Each Company
maintains its own chart of accounts, journal entries, and financial
statements.  A single Tenant may operate several Companies (e.g. multiple
legal entities or subsidiaries).

Table relationships
-------------------
    tenants  1──* companies
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cairnbooks.db import Base


def _utcnow() -> datetime:
    """Return the current UTC-aware datetime (used as a column default)."""
    return datetime.now(UTC)


class Tenant(Base):
    """Top-level multi-tenancy boundary.

    Attributes:
        id:         UUID primary key.
        name:       Human-readable display name (e.g. "Acme Corp").
        slug:       URL-safe unique identifier (e.g. "acme-corp").
        created_at: Timestamp of record creation (UTC, timezone-aware).
        updated_at: Timestamp of last modification (UTC, timezone-aware).
        companies:  Back-reference to all :class:`Company` rows owned by
                    this Tenant.
    """

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    companies: Mapped[list[Company]] = relationship(
        "Company",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Tenant id={self.id!s} slug={self.slug!r}>"


class Company(Base):
    """A bookkeeping entity (legal entity / business) owned by a :class:`Tenant`.

    Attributes:
        id:                   UUID primary key.
        tenant_id:            FK to :attr:`Tenant.id`.
        name:                 Trading / display name (e.g. "Acme Widgets").
        legal_name:           Optional full legal name (e.g. "Acme Widgets LLC").
        currency:             ISO 4217 three-letter currency code; default "USD".
        fiscal_year_end_month: Month number (1–12) on which the fiscal year ends;
                              default 12 (December).
        created_at:           Timestamp of record creation (UTC, timezone-aware).
        updated_at:           Timestamp of last modification (UTC, timezone-aware).
        tenant:               Relationship back to the owning :class:`Tenant`.
    """

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    fiscal_year_end_month: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=12
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "fiscal_year_end_month BETWEEN 1 AND 12",
            name="ck_companies_fiscal_year_end_month",
        ),
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="companies")

    def __repr__(self) -> str:
        return f"<Company id={self.id!s} name={self.name!r}>"
