"""create accounts table (chart of accounts)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-07 00:00:00.000000

Creates:
  * account_type  Postgres enum  (asset | liability | equity | income | expense)
  * normal_balance Postgres enum (debit | credit)
  * accounts table with self-referential parent_id FK and (company_id, code)
    unique constraint.
"""

import sqlalchemy as sa

from alembic import op

# ── Revision identifiers ────────────────────────────────────────────────────
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    account_type_enum = sa.Enum(
        "asset",
        "liability",
        "equity",
        "income",
        "expense",
        name="account_type",
    )
    normal_balance_enum = sa.Enum(
        "debit",
        "credit",
        name="normal_balance",
    )
    account_type_enum.create(op.get_bind(), checkfirst=True)
    normal_balance_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column(
            "code",
            sa.String(20),
            nullable=False,
            comment="Alphanumeric account code (e.g. '1000', '4100').",
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "asset",
                "liability",
                "equity",
                "income",
                "expense",
                name="account_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "normal_balance",
            sa.Enum(
                "debit",
                "credit",
                name="normal_balance",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
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
            name=op.f("fk_accounts_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["accounts.id"],
            name=op.f("fk_accounts_parent_id_accounts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),
    )
    op.create_index(
        op.f("ix_accounts_company_id"),
        "accounts",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_accounts_parent_id"),
        "accounts",
        ["parent_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_accounts_parent_id"), table_name="accounts")
    op.drop_index(op.f("ix_accounts_company_id"), table_name="accounts")
    op.drop_table("accounts")
    # Drop enum types after the table is gone.
    sa.Enum(name="normal_balance").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="account_type").drop(op.get_bind(), checkfirst=True)
