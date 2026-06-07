"""Create journals and journal_lines tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-07 00:00:00.000000

Introduces the double-entry journal tables.

Table: journals
---------------
id          UUID primary key (gen_random_uuid()).
company_id  UUID, not null — FK → companies.id ON DELETE CASCADE.
date        DATE, not null — accounting date of the entry.
reference   VARCHAR(255), nullable — optional external reference.
description TEXT, nullable — optional free-text description.
status      VARCHAR(20), not null, default 'draft' — draft | posted.
created_at  TIMESTAMPTZ, not null, server default NOW().
updated_at  TIMESTAMPTZ, not null, server default NOW().

Table: journal_lines
--------------------
id          UUID primary key (gen_random_uuid()).
journal_id  UUID, not null — FK → journals.id ON DELETE CASCADE.
account_id  UUID, not null — FK → accounts.id ON DELETE RESTRICT.
debit       NUMERIC(19,4), not null, default 0 — debit amount (≥ 0).
credit      NUMERIC(19,4), not null, default 0 — credit amount (≥ 0).
description TEXT, nullable — optional line-level memo.
line_number INTEGER, not null, default 1 — 1-based ordering within journal.
created_at  TIMESTAMPTZ, not null, server default NOW().

Constraints
-----------
fk_journals_company_id              — journals.company_id → companies.id CASCADE.
ck_journals_status                  — status IN ('draft', 'posted').
fk_journal_lines_journal_id         — journal_lines.journal_id → journals.id CASCADE.
fk_journal_lines_account_id         — journal_lines.account_id → accounts.id RESTRICT.
ck_journal_lines_debit_nonneg       — debit >= 0.
ck_journal_lines_credit_nonneg      — credit >= 0.

Indexes
-------
ix_journals_company_id              — btree on company_id.
ix_journals_company_date            — composite (company_id, date).
ix_journal_lines_journal_id         — btree on journal_id.
ix_journal_lines_account_id         — btree on account_id.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create journals and journal_lines tables."""
    # ── journals ─────────────────────────────────────────────────────────────
    op.create_table(
        "journals",
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
            comment="Owning company; journals are isolated per company.",
        ),
        sa.Column(
            "date",
            sa.Date(),
            nullable=False,
            comment="Accounting date of the entry.",
        ),
        sa.Column(
            "reference",
            sa.String(255),
            nullable=True,
            comment="Optional external reference (e.g. invoice number).",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Optional free-text description of the entry.",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
            comment="Lifecycle status: draft | posted.",
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
            name="fk_journals_company_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'posted')",
            name="ck_journals_status",
        ),
    )

    op.create_index("ix_journals_company_id", "journals", ["company_id"])
    op.create_index("ix_journals_company_date", "journals", ["company_id", "date"])

    # ── journal_lines ─────────────────────────────────────────────────────────
    op.create_table(
        "journal_lines",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="UUID primary key.",
        ),
        sa.Column(
            "journal_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="Parent journal entry.",
        ),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="Account receiving this debit/credit.",
        ),
        sa.Column(
            "debit",
            sa.Numeric(precision=19, scale=4),
            nullable=False,
            server_default="0",
            comment="Debit amount (≥ 0).",
        ),
        sa.Column(
            "credit",
            sa.Numeric(precision=19, scale=4),
            nullable=False,
            server_default="0",
            comment="Credit amount (≥ 0).",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Optional line-level description / memo.",
        ),
        sa.Column(
            "line_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="1-based ordering of lines within the journal.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Row insertion timestamp (UTC).",
        ),
        # ── Constraints ──────────────────────────────────────────────────────
        sa.ForeignKeyConstraint(
            ["journal_id"],
            ["journals.id"],
            name="fk_journal_lines_journal_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_journal_lines_account_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("debit >= 0", name="ck_journal_lines_debit_nonneg"),
        sa.CheckConstraint("credit >= 0", name="ck_journal_lines_credit_nonneg"),
    )

    op.create_index("ix_journal_lines_journal_id", "journal_lines", ["journal_id"])
    op.create_index("ix_journal_lines_account_id", "journal_lines", ["account_id"])


def downgrade() -> None:
    """Drop journal_lines then journals (child before parent)."""
    op.drop_index("ix_journal_lines_account_id", table_name="journal_lines")
    op.drop_index("ix_journal_lines_journal_id", table_name="journal_lines")
    op.drop_table("journal_lines")

    op.drop_index("ix_journals_company_date", table_name="journals")
    op.drop_index("ix_journals_company_id", table_name="journals")
    op.drop_table("journals")
