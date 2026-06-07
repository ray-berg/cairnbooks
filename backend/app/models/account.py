"""Account model — a node in the chart of accounts tree for a Company."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.company import Company


class AccountType(enum.StrEnum):
    """The five fundamental account types in double-entry bookkeeping."""

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class NormalBalance(enum.StrEnum):
    """The side of the ledger that increases the account balance."""

    DEBIT = "debit"
    CREDIT = "credit"


# Derived normal balance for each account type (accounting convention).
_NORMAL_BALANCE_MAP: dict[AccountType, NormalBalance] = {
    AccountType.ASSET: NormalBalance.DEBIT,
    AccountType.LIABILITY: NormalBalance.CREDIT,
    AccountType.EQUITY: NormalBalance.CREDIT,
    AccountType.INCOME: NormalBalance.CREDIT,
    AccountType.EXPENSE: NormalBalance.DEBIT,
}


def default_normal_balance(account_type: AccountType) -> NormalBalance:
    """Return the conventional normal balance for *account_type*."""
    return _NORMAL_BALANCE_MAP[account_type]


class Account(Base):
    """A single account in the chart of accounts.

    Accounts form a tree via the self-referential ``parent_id`` FK.
    Each account belongs to exactly one :class:`~app.models.company.Company`.
    """

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional parent for hierarchical COA (header / summary accounts)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        comment="Alphanumeric account code (e.g. '1000', '4100').",
    )
    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    type: Mapped[AccountType] = mapped_column(
        sa.Enum(AccountType, name="account_type", create_type=True),
        nullable=False,
    )
    normal_balance: Mapped[NormalBalance] = mapped_column(
        sa.Enum(NormalBalance, name="normal_balance", create_type=True),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.true(),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    # ── Table constraints ─────────────────────────────────────────────────────
    __table_args__ = (
        # Account codes must be unique within a company.
        sa.UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    company: Mapped[Company] = relationship(
        "Company",
        back_populates="accounts",
    )
    parent: Mapped[Account | None] = relationship(
        "Account",
        remote_side="Account.id",
        back_populates="children",
        foreign_keys="Account.parent_id",
    )
    children: Mapped[list[Account]] = relationship(
        "Account",
        back_populates="parent",
        foreign_keys="Account.parent_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Account id={self.id!s} code={self.code!r} "
            f"name={self.name!r} type={self.type.value!r}>"
        )
