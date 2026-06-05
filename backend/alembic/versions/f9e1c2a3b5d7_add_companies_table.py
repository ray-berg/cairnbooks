"""add companies table

Revision ID: f9e1c2a3b5d7
Revises: b1f11f1309c9
Create Date: 2026-06-05 22:50:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f9e1c2a3b5d7'
down_revision: Union[str, Sequence[str], None] = 'b1f11f1309c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the companies table."""
    op.create_table(
        'companies',
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
        sa.PrimaryKeyConstraint('id', name='pk_companies'),
    )
    op.create_index(
        'ix_companies_tenant_id',
        'companies',
        ['tenant_id'],
        unique=False,
    )


def downgrade() -> None:
    """Drop the companies table."""
    op.drop_index('ix_companies_tenant_id', table_name='companies')
    op.drop_table('companies')
