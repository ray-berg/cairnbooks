"""create fiscal_periods table

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-07 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# ── Revision identifiers ────────────────────────────────────────────────────
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels = None
depends_on = None

# ── Enum type ───────────────────────────────────────────────────────────────
period_status = sa.Enum("open", "closed", name="period_status")


def upgrade() -> None:
    period_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "fiscal_periods",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column(
            "name",
            sa.String(100),
            nullable=False,
            comment="Human-readable label, e.g. 'Q1 2026' or 'FY 2025'.",
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
            sa.Enum("open", "closed", name="period_status", create_type=False),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_fiscal_periods_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fiscal_periods")),
    )
    op.create_index(
        op.f("ix_fiscal_periods_company_id"),
        "fiscal_periods",
        ["company_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_fiscal_periods_company_id"), table_name="fiscal_periods")
    op.drop_table("fiscal_periods")
    period_status.drop(op.get_bind(), checkfirst=True)
