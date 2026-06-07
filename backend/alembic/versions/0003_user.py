"""create roles, users, and user_roles tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-07 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_roles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_user_roles_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_user_roles_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", "tenant_id", name=op.f("pk_user_roles")),
    )
    op.create_index(
        op.f("ix_user_roles_tenant_id"),
        "user_roles",
        ["tenant_id"],
        unique=False,
    )

    # Seed built-in roles with deterministic UUIDs
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", sa.UUID),
            sa.column("name", sa.String),
            sa.column("description", sa.String),
        ),
        [
            {
                "id": "10000000-0000-0000-0000-000000000001",
                "name": "admin",
                "description": "Full administrative access",
            },
            {
                "id": "10000000-0000-0000-0000-000000000002",
                "name": "accountant",
                "description": "Create and manage journal entries and reports",
            },
            {
                "id": "10000000-0000-0000-0000-000000000003",
                "name": "viewer",
                "description": "Read-only access to reports and data",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_roles_tenant_id"), table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("roles")
