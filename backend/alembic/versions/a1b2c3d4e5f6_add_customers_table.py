"""add customers table

Revision ID: a1b2c3d4e5f6
Revises: f9e1c2a3b5d7
Create Date: 2026-06-05 23:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f9e1c2a3b5d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the customers table."""
    op.create_table(
        'customers',
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
            'company_id',
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
            sa.String(length=254),
            nullable=True,
        ),
        sa.Column(
            'phone',
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            'is_active',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
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
        sa.ForeignKeyConstraint(
            ['company_id'],
            ['companies.id'],
            name='fk_customers_company_id',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_customers'),
    )
    op.create_index(
        'ix_customers_tenant_id',
        'customers',
        ['tenant_id'],
        unique=False,
    )
    op.create_index(
        'ix_customers_company_id',
        'customers',
        ['company_id'],
        unique=False,
    )


def downgrade() -> None:
    """Drop the customers table."""
    op.drop_index('ix_customers_company_id', table_name='customers')
    op.drop_index('ix_customers_tenant_id', table_name='customers')
    op.drop_table('customers')
