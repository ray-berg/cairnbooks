"""Reusable SQLAlchemy column mixins.

These are mixed into ORM model classes (alongside :class:`~app.db.session.Base`)
to provide shared column definitions that apply across many tables.

Usage::

    from app.db.session import Base
    from app.db.mixins import TenantMixin

    class MyModel(TenantMixin, Base):
        __tablename__ = "my_table"
        ...
"""
from __future__ import annotations

import uuid

from sqlalchemy import UUID
from sqlalchemy.orm import Mapped, mapped_column


class TenantMixin:
    """Adds ``tenant_id`` for row-level tenant isolation.

    Apply this mixin to every model that belongs to a single tenant so that
    every row is stamped with the owning organisation's UUID.  The column is
    indexed to make tenant-scoped queries efficient.

    The application layer is responsible for setting ``tenant_id`` on new
    instances and for filtering queries by ``tenant_id`` (or delegating that
    to a tenant-aware session subclass — see architecture doc §6.3).
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="UUID of the owning tenant / organisation.",
    )
