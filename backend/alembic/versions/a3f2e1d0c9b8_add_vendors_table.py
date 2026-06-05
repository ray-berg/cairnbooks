"""add vendors table

Revision ID: a3f2e1d0c9b8
Revises: f9e1c2a3b5d7
Create Date: 2026-06-05 23:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3f2e1d0c9b8'
down_revision: Union[str, Sequence[str], None] = 'f9e1c2a3b5d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the vendors table."""
    op.create_table(
        'vendors',
        sa.Column(
            'tenant_id',
            sa.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            'id',
            sa.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            'name',
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            'email',
            sa.String(length=320),
            nullable=True,
        ),
        sa.Column(
            'phone',
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            'website',
            sa.String(length=2048),
            nullable=True,
        ),
        sa.Column(
            'address_line1',
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            'address_line2',
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            'city',
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            'state',
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            'postal_code',
            sa.String(length=20),
            nullable=True,
        ),
        sa.Column(
            'country',
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id', name='pk_vendors'),
    )
    op.create_index(
        'ix_vendors_tenant_id',
        'vendors',
        ['tenant_id'],
        unique=False,
    )


def downgrade() -> None:
    """Drop the vendors table."""
    op.drop_index('ix_vendors_tenant_id', table_name='vendors')
    op.drop_table('vendors')
