"""Create fiscal_periods table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-07 00:00:00.000000

Introduces the ``fiscal_periods`` table.  A fiscal period represents a named
accounting period (e.g. "January 2026", "2026-Q1") with an ``open`` / ``closed``
lifecycle.  Once closed, the application blocks new journal postings whose
accounting date falls within the period's ``[start_date, end_date]`` range.

Table: fiscal_periods
---------------------
id          UUID primary key (gen_random_uuid()).
company_id  UUID, not null — FK → companies.id ON DELETE CASCADE.
name        VARCHAR(100), not null — human-readable label.
start_date  DATE, not null — first day of the period (inclusive).
end_date    DATE, not null — last day of the period (inclusive).
status      VARCHAR(20), not null, default 'open' — open | closed.
closed_at   TIMESTAMPTZ, nullable — populated when status transitions to closed.
created_at  TIMESTAMPTZ, not null, server default NOW().
updated_at  TIMESTAMPTZ, not null, server default NOW().

Constraints
-----------
fk_fiscal_periods_company_id    — company_id → companies.id CASCADE.
ck_fiscal_periods_status        — status IN ('open', 'closed').
ck_fiscal_periods_date_range    — end_date >= start_date.

Indexes
-------
ix_fiscal_periods_company_id     — btree on company_id.
ix_fiscal_periods_company_dates  — composite (company_id, start_date, end_date).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the fiscal_periods table."""
    op.create_table(
        "fiscal_periods",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="UUID primary key.",
        ),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="Owning company; fiscal periods are isolated per company.",
        ),
        sa.Column(
            "name",
            sa.String(100),
            nullable=False,
            comment="Human-readable period label (e.g. '2026-Q1', 'January 2026').",
        ),
        sa.Column(
            "start_date",
            sa.Date(),
            nullable=False,
            comment="First day of the period (inclusive).",
        ),
        sa.Column(
            "end_date",
            sa.Date(),
            nullable=False,
            comment="Last day of the period (inclusive).",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="open",
            comment="Lifecycle status: open | closed.",
        ),
        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when the period was closed (UTC). NULL while open.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Row insertion timestamp (UTC).",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Last-update timestamp (UTC).",
        ),
        # ── Constraints ──────────────────────────────────────────────────────
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_fiscal_periods_company_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'closed')",
            name="ck_fiscal_periods_status",
        ),
        sa.CheckConstraint(
            "end_date >= start_date",
            name="ck_fiscal_periods_date_range",
        ),
    )

    op.create_index("ix_fiscal_periods_company_id", "fiscal_periods", ["company_id"])
    op.create_index(
        "ix_fiscal_periods_company_dates",
        "fiscal_periods",
        ["company_id", "start_date", "end_date"],
    )


def downgrade() -> None:
    """Drop the fiscal_periods table."""
    op.drop_index("ix_fiscal_periods_company_dates", table_name="fiscal_periods")
    op.drop_index("ix_fiscal_periods_company_id", table_name="fiscal_periods")
    op.drop_table("fiscal_periods")
