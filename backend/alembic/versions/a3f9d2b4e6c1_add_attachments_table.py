"""add attachments table

Revision ID: a3f9d2b4e6c1
Revises: f9e1c2a3b5d7
Create Date: 2026-06-05 23:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f9d2b4e6c1"
down_revision: Union[str, Sequence[str], None] = "f9e1c2a3b5d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the attachments table."""
    op.create_table(
        "attachments",
        sa.Column(
            "tenant_id",
            sa.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "filename",
            sa.String(length=512),
            nullable=False,
        ),
        sa.Column(
            "content_type",
            sa.String(length=256),
            nullable=False,
        ),
        sa.Column(
            "size_bytes",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "object_key",
            sa.String(length=1024),
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
        sa.PrimaryKeyConstraint("id", name="pk_attachments"),
        sa.UniqueConstraint("object_key", name="uq_attachments_object_key"),
    )
    op.create_index(
        "ix_attachments_tenant_id",
        "attachments",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_attachments_source_type",
        "attachments",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "ix_attachments_source_id",
        "attachments",
        ["source_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the attachments table."""
    op.drop_index("ix_attachments_source_id", table_name="attachments")
    op.drop_index("ix_attachments_source_type", table_name="attachments")
    op.drop_index("ix_attachments_tenant_id", table_name="attachments")
    op.drop_table("attachments")
