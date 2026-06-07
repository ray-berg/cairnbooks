"""Role model and built-in role seeds.

Three built-in roles are defined:
  * **admin**       – full administrative access
  * **accountant**  – create and manage journal entries and reports
  * **viewer**      – read-only access to reports and data
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.user_role import UserRole


class RoleName(StrEnum):
    """Canonical names for the three built-in roles."""

    admin = "admin"
    accountant = "accountant"
    viewer = "viewer"


_BUILTIN_ROLES: list[dict[str, str]] = [
    {"name": RoleName.admin.value, "description": "Full administrative access"},
    {
        "name": RoleName.accountant.value,
        "description": "Create and manage journal entries and reports",
    },
    {"name": RoleName.viewer.value, "description": "Read-only access to reports and data"},
]


class Role(Base):
    """An authorization role that can be assigned to users within a tenant."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(sa.String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    user_roles: Mapped[list[UserRole]] = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id!s} name={self.name!r}>"


def seed_roles(session: sa.orm.Session) -> list[Role]:
    """Insert the three built-in roles if they do not already exist.

    Idempotent: safe to call multiple times.
    """
    roles: list[Role] = []
    for role_data in _BUILTIN_ROLES:
        role = session.execute(
            select(Role).where(Role.name == role_data["name"])
        ).scalar_one_or_none()
        if role is None:
            role = Role(**role_data)
            session.add(role)
        roles.append(role)
    session.flush()
    return roles
