"""Create accounts table (Chart of Accounts).

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-06 00:00:00.000000

Introduces the ``accounts`` table — the Chart of Accounts.

Table: accounts
---------------
id          UUID primary key (gen_random_uuid()).
company_id  UUID, not null — FK → companies.id ON DELETE CASCADE.
code        VARCHAR(50), not null — account code, unique per company.
name        VARCHAR(255), not null — human-readable label.
type        VARCHAR(20), not null — one of: asset | liability | equity |
            income | expense.
parent_id   UUID, nullable — self-referential FK → accounts.id for
            the account hierarchy.
active      BOOLEAN, not null, default TRUE — archived flag.
created_at  TIMESTAMPTZ, not null, server default NOW().
updated_at  TIMESTAMPTZ, not null, server default NOW().

Constraints
-----------
fk_accounts_company_id      — accounts.company_id → companies.id CASCADE.
fk_accounts_parent_id       — accounts.parent_id → accounts.id RESTRICT.
ck_accounts_no_self_parent  — parent_id IS NULL OR parent_id <> id.
uq_accounts_company_code    — UNIQUE(company_id, code).

Indexes
-------
ix_accounts_company_id              — btree on company_id.
ix_accounts_parent_id               — btree on parent_id.
ix_accounts_type                    — btree on type.
ix_accounts_company_type_active     — composite (company_id, type, active).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the accounts table."""
    op.create_table(
        "accounts",
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
            comment="Owning company; accounts are isolated per company.",
        ),
        sa.Column(
            "code",
            sa.String(50),
            nullable=False,
            comment="Short account code, unique within a company.",
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Human-readable account name.",
        ),
        sa.Column(
            "type",
            sa.String(20),
            nullable=False,
            comment="Account type: asset | liability | equity | income | expense.",
        ),
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Parent account id; NULL for top-level (header) accounts.",
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="False means archived; account cannot receive new postings.",
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
        # ── Constraints ──────────────────────────────────────────────────
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_accounts_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["accounts.id"],
            name="fk_accounts_parent_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_accounts_no_self_parent",
        ),
        sa.UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),
    )

    # ── Indexes ──────────────────────────────────────────────────────────
    op.create_index("ix_accounts_company_id", "accounts", ["company_id"])
    op.create_index("ix_accounts_parent_id", "accounts", ["parent_id"])
    op.create_index("ix_accounts_type", "accounts", ["type"])
    op.create_index(
        "ix_accounts_company_type_active",
        "accounts",
        ["company_id", "type", "active"],
    )


def downgrade() -> None:
    """Drop the accounts table and its indexes."""
    op.drop_index("ix_accounts_company_type_active", table_name="accounts")
    op.drop_index("ix_accounts_type", table_name="accounts")
    op.drop_index("ix_accounts_parent_id", table_name="accounts")
    op.drop_index("ix_accounts_company_id", table_name="accounts")
    op.drop_table("accounts")
