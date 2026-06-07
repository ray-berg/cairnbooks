"""Create items table (Products and Services).

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-07 00:00:00.000000

Introduces the ``items`` table — the Product/Service catalogue.

An Item represents a product or service that a company sells (income) or
purchases (expense).  It links to up to two accounts from the Chart of
Accounts:

* ``income_account_id``  — revenue account credited on sales invoices.
* ``expense_account_id`` — cost/expense account debited on bills.

Both account links are optional and cascade-null when the referenced account
is deleted (SET NULL), preserving item history.

Table: items
------------
id                  UUID primary key (gen_random_uuid()).
company_id          UUID, not null — FK → companies.id ON DELETE CASCADE.
name                VARCHAR(255), not null — product/service display name.
description         TEXT, nullable — optional longer description.
income_account_id   UUID, nullable — FK → accounts.id ON DELETE SET NULL.
expense_account_id  UUID, nullable — FK → accounts.id ON DELETE SET NULL.
active              BOOLEAN, not null, default TRUE — archived flag.
created_at          TIMESTAMPTZ, not null, server default NOW().
updated_at          TIMESTAMPTZ, not null, server default NOW().

Constraints
-----------
fk_items_company_id         — items.company_id → companies.id CASCADE.
fk_items_income_account_id  — items.income_account_id → accounts.id SET NULL.
fk_items_expense_account_id — items.expense_account_id → accounts.id SET NULL.

Indexes
-------
ix_items_company_id          — btree on company_id.
ix_items_income_account_id   — btree on income_account_id.
ix_items_expense_account_id  — btree on expense_account_id.
ix_items_company_active      — composite (company_id, active).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the items table."""
    op.create_table(
        "items",
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
            comment="Owning company; items are isolated per company.",
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Product or service name.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Optional longer description.",
        ),
        sa.Column(
            "income_account_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Revenue account credited when this item is sold.",
        ),
        sa.Column(
            "expense_account_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Cost/expense account debited when this item is purchased.",
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="False means archived; item should not appear in new documents.",
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
            name="fk_items_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["income_account_id"],
            ["accounts.id"],
            name="fk_items_income_account_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["expense_account_id"],
            ["accounts.id"],
            name="fk_items_expense_account_id",
            ondelete="SET NULL",
        ),
    )

    # ── Indexes ──────────────────────────────────────────────────────────
    op.create_index("ix_items_company_id", "items", ["company_id"])
    op.create_index("ix_items_income_account_id", "items", ["income_account_id"])
    op.create_index("ix_items_expense_account_id", "items", ["expense_account_id"])
    op.create_index("ix_items_company_active", "items", ["company_id", "active"])


def downgrade() -> None:
    """Drop the items table and its indexes."""
    op.drop_index("ix_items_company_active", table_name="items")
    op.drop_index("ix_items_expense_account_id", table_name="items")
    op.drop_index("ix_items_income_account_id", table_name="items")
    op.drop_index("ix_items_company_id", table_name="items")
    op.drop_table("items")
