"""User ORM model.

Users authenticate to the application with an e-mail address and bcrypt
password hash.  A coarse-grained ``role`` column drives initial authorisation
checks; fine-grained tenant membership will be introduced in a later migration.

Valid role values
-----------------
``admin``
    Full system access — can manage tenants, users, and all accounting data.
``bookkeeper``
    Can create and edit journal entries, chart-of-accounts, etc.
``viewer``
    Read-only access to reports and statements (default for new users).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from cairnbooks.db import Base

# ---------------------------------------------------------------------------
# Valid role literals — used in the check constraint and Python validation
# ---------------------------------------------------------------------------
VALID_ROLES: frozenset[str] = frozenset({"admin", "bookkeeper", "viewer"})
DEFAULT_ROLE: str = "viewer"


def _utcnow() -> datetime:
    """Return the current UTC-aware datetime (used as a column default)."""
    return datetime.now(UTC)


class User(Base):
    """System user that can authenticate to CairnBooks.

    Attributes:
        id:            UUID primary key.
        email:         Unique e-mail address used for login (case-sensitive
                       as stored; callers should normalise to lower-case before
                       writing).
        password_hash: Bcrypt hash of the user's password produced by
                       :func:`cairnbooks.security.passwords.hash_password`.
        role:          Coarse-grained access role: ``"admin"``,
                       ``"bookkeeper"``, or ``"viewer"`` (default).
        created_at:    Timestamp of record creation (UTC, timezone-aware).
        updated_at:    Timestamp of last modification (UTC, timezone-aware).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=DEFAULT_ROLE,
        server_default=DEFAULT_ROLE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'bookkeeper', 'viewer')",
            name="ck_users_role",
        ),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!s} email={self.email!r} role={self.role!r}>"
