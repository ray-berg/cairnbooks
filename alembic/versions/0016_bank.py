"""Create bank_accounts table (BankAccount linked to GL account).

Revision ID: 0016
Revises: 0005
Create Date: 2026-06-07 00:00:00.000000

Introduces the ``bank_accounts`` table, which stores real-world bank accounts
for a Company.  Each bank account is linked to a GL account in the Chart of
Accounts (``accounts.id``) so that transactions can be double-entry posted.

Table: bank_accounts
--------------------
id              UUID primary key (gen_random_uuid()).
company_id      UUID, not null — FK → companies.id ON DELETE CASCADE.
gl_account_id   UUID, not null — FK → accounts.id ON DELETE RESTRICT.
name            VARCHAR(255), not null — label, unique per company.
account_number  VARCHAR(50), nullable — bank account number.
routing_number  VARCHAR(20), nullable — ABA routing number.
bank_name       VARCHAR(255), nullable — financial institution name.
currency        VARCHAR(3), not null, default 'USD' — ISO 4217 code.
active          BOOLEAN, not null, default TRUE — archived flag.
created_at      TIMESTAMPTZ, not null, server default NOW().
updated_at      TIMESTAMPTZ, not null, server default NOW().

Constraints
-----------
fk_bank_accounts_company_id     — bank_accounts.company_id → companies.id CASCADE.
fk_bank_accounts_gl_account_id  — bank_accounts.gl_account_id → accounts.id RESTRICT.
uq_bank_accounts_company_name   — UNIQUE(company_id, name).

Indexes
-------
ix_bank_accounts_company_id         — btree on company_id.
ix_bank_accounts_gl_account_id      — btree on gl_account_id.
ix_bank_accounts_company_active     — composite (company_id, active).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "0016"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the bank_accounts table and its indexes."""
    op.create_table(
        "bank_accounts",
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
            comment="Owning company; bank accounts are isolated per company.",
        ),
        sa.Column(
            "gl_account_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="Linked GL account from the Chart of Accounts.",
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Human-readable bank account name (e.g. 'Main Checking').",
        ),
        sa.Column(
            "account_number",
            sa.String(50),
            nullable=True,
            comment="Bank account number (plain or masked).",
        ),
        sa.Column(
            "routing_number",
            sa.String(20),
            nullable=True,
            comment="ABA routing / transit number.",
        ),
        sa.Column(
            "bank_name",
            sa.String(255),
            nullable=True,
            comment="Name of the financial institution.",
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default="USD",
            comment="ISO 4217 currency code.",
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="False means archived; account unavailable for new transactions.",
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
        # ── Foreign keys ─────────────────────────────────────────────────
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_bank_accounts_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["gl_account_id"],
            ["accounts.id"],
            name="fk_bank_accounts_gl_account_id",
            ondelete="RESTRICT",
        ),
        # ── Unique constraints ────────────────────────────────────────────
        sa.UniqueConstraint("company_id", "name", name="uq_bank_accounts_company_name"),
    )

    # ── Indexes ───────────────────────────────────────────────────────────
    op.create_index("ix_bank_accounts_company_id", "bank_accounts", ["company_id"])
    op.create_index("ix_bank_accounts_gl_account_id", "bank_accounts", ["gl_account_id"])
    op.create_index(
        "ix_bank_accounts_company_active",
        "bank_accounts",
        ["company_id", "active"],
    )


def downgrade() -> None:
    """Drop the bank_accounts table and its indexes."""
    op.drop_index("ix_bank_accounts_company_active", table_name="bank_accounts")
    op.drop_index("ix_bank_accounts_gl_account_id", table_name="bank_accounts")
    op.drop_index("ix_bank_accounts_company_id", table_name="bank_accounts")
    op.drop_table("bank_accounts")
