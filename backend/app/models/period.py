"""FiscalPeriod model — a named accounting period belonging to a Company."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.company import Company


class PeriodStatus(StrEnum):
    """Lifecycle status of a fiscal period."""

    OPEN = "open"
    CLOSED = "closed"


class FiscalPeriod(Base):
    """A named date-range accounting period scoped to a Company.

    Periods are used to control which dates journal entries may be posted to.
    A *closed* period rejects new postings; only *open* periods accept them.
    """

    __tablename__ = "fiscal_periods"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        sa.String(100),
        nullable=False,
        comment="Human-readable label, e.g. 'Q1 2026' or 'FY 2025'.",
    )
    start_date: Mapped[date] = mapped_column(
        sa.Date(),
        nullable=False,
        comment="First day of the period (inclusive).",
    )
    end_date: Mapped[date] = mapped_column(
        sa.Date(),
        nullable=False,
        comment="Last day of the period (inclusive).",
    )
    status: Mapped[PeriodStatus] = mapped_column(
        sa.Enum(PeriodStatus, name="period_status"),
        nullable=False,
        server_default=PeriodStatus.OPEN.value,
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
    company: Mapped[Company] = relationship(
        "Company",
        back_populates="fiscal_periods",
    )

    def __repr__(self) -> str:
        return (
            f"<FiscalPeriod id={self.id!s} name={self.name!r} "
            f"status={self.status.value!r} company_id={self.company_id!s}>"
        )
