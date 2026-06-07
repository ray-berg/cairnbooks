"""Default chart of accounts seed function.

Call :func:`seed_default_coa` after a new :class:`~app.models.company.Company`
is created to populate it with a standard small-business chart of accounts.
The COA follows a typical US-style numbering scheme:

  1000-1999  Assets
  2000-2999  Liabilities
  3000-3999  Equity
  4000-4999  Income
  5000-5999  Expenses

Header / summary accounts (no ``parent_id``) group the detail accounts beneath
them.  The function is **idempotent**: it skips any account whose
``(company_id, code)`` pair already exists, so it is safe to call more than
once (e.g. during re-seeding or testing).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.account import Account, AccountType, NormalBalance, default_normal_balance

# ---------------------------------------------------------------------------
# Internal seed data structure
# ---------------------------------------------------------------------------


@dataclass
class _AccountDef:
    """Flat description of one account in the seed tree."""

    code: str
    name: str
    type: AccountType
    normal_balance: NormalBalance | None = None  # None → use convention
    description: str | None = None
    children: list[_AccountDef] = field(default_factory=list)

    def resolved_normal_balance(self) -> NormalBalance:
        """Return explicit override or the conventional balance for this type."""
        if self.normal_balance is not None:
            return self.normal_balance
        return default_normal_balance(self.type)


# ---------------------------------------------------------------------------
# Seed tree
# ---------------------------------------------------------------------------

_SEED: list[_AccountDef] = [
    # ── Assets ───────────────────────────────────────────────────────────────
    _AccountDef(
        code="1000",
        name="Assets",
        type=AccountType.ASSET,
        description="All asset accounts.",
        children=[
            _AccountDef(
                code="1100",
                name="Cash and Cash Equivalents",
                type=AccountType.ASSET,
                children=[
                    _AccountDef(code="1110", name="Checking Account", type=AccountType.ASSET),
                    _AccountDef(code="1120", name="Savings Account", type=AccountType.ASSET),
                    _AccountDef(code="1130", name="Petty Cash", type=AccountType.ASSET),
                ],
            ),
            _AccountDef(
                code="1200",
                name="Accounts Receivable",
                type=AccountType.ASSET,
                description="Amounts owed by customers.",
            ),
            _AccountDef(
                code="1300",
                name="Inventory",
                type=AccountType.ASSET,
                description="Goods held for sale.",
            ),
            _AccountDef(
                code="1400",
                name="Prepaid Expenses",
                type=AccountType.ASSET,
                description="Expenses paid in advance.",
            ),
            _AccountDef(
                code="1500",
                name="Property and Equipment",
                type=AccountType.ASSET,
                children=[
                    _AccountDef(code="1510", name="Equipment", type=AccountType.ASSET),
                    _AccountDef(
                        code="1520",
                        name="Accumulated Depreciation",
                        type=AccountType.ASSET,
                        normal_balance=NormalBalance.CREDIT,
                        description="Contra-asset: total depreciation charged to date.",
                    ),
                ],
            ),
            _AccountDef(
                code="1900",
                name="Other Assets",
                type=AccountType.ASSET,
            ),
        ],
    ),
    # ── Liabilities ──────────────────────────────────────────────────────────
    _AccountDef(
        code="2000",
        name="Liabilities",
        type=AccountType.LIABILITY,
        description="All liability accounts.",
        children=[
            _AccountDef(
                code="2100",
                name="Current Liabilities",
                type=AccountType.LIABILITY,
                children=[
                    _AccountDef(
                        code="2110",
                        name="Accounts Payable",
                        type=AccountType.LIABILITY,
                        description="Amounts owed to vendors.",
                    ),
                    _AccountDef(
                        code="2120",
                        name="Accrued Liabilities",
                        type=AccountType.LIABILITY,
                    ),
                    _AccountDef(
                        code="2130",
                        name="Sales Tax Payable",
                        type=AccountType.LIABILITY,
                    ),
                    _AccountDef(
                        code="2140",
                        name="Payroll Liabilities",
                        type=AccountType.LIABILITY,
                    ),
                    _AccountDef(
                        code="2150",
                        name="Short-term Loans Payable",
                        type=AccountType.LIABILITY,
                    ),
                ],
            ),
            _AccountDef(
                code="2200",
                name="Long-term Liabilities",
                type=AccountType.LIABILITY,
                children=[
                    _AccountDef(
                        code="2210",
                        name="Long-term Loans Payable",
                        type=AccountType.LIABILITY,
                    ),
                ],
            ),
        ],
    ),
    # ── Equity ───────────────────────────────────────────────────────────────
    _AccountDef(
        code="3000",
        name="Equity",
        type=AccountType.EQUITY,
        description="All equity accounts.",
        children=[
            _AccountDef(code="3100", name="Common Stock", type=AccountType.EQUITY),
            _AccountDef(code="3200", name="Retained Earnings", type=AccountType.EQUITY),
            _AccountDef(
                code="3300",
                name="Owner's Draw",
                type=AccountType.EQUITY,
                normal_balance=NormalBalance.DEBIT,
                description="Contra-equity: distributions to the owner.",
            ),
        ],
    ),
    # ── Income ───────────────────────────────────────────────────────────────
    _AccountDef(
        code="4000",
        name="Income",
        type=AccountType.INCOME,
        description="All income / revenue accounts.",
        children=[
            _AccountDef(code="4100", name="Sales Revenue", type=AccountType.INCOME),
            _AccountDef(code="4200", name="Service Revenue", type=AccountType.INCOME),
            _AccountDef(code="4900", name="Other Income", type=AccountType.INCOME),
        ],
    ),
    # ── Expenses ─────────────────────────────────────────────────────────────
    _AccountDef(
        code="5000",
        name="Expenses",
        type=AccountType.EXPENSE,
        description="All operating expense accounts.",
        children=[
            _AccountDef(
                code="5100",
                name="Cost of Goods Sold",
                type=AccountType.EXPENSE,
                description="Direct costs of goods or services sold.",
            ),
            _AccountDef(code="5200", name="Salaries and Wages", type=AccountType.EXPENSE),
            _AccountDef(code="5300", name="Rent Expense", type=AccountType.EXPENSE),
            _AccountDef(code="5400", name="Utilities", type=AccountType.EXPENSE),
            _AccountDef(code="5500", name="Office Supplies", type=AccountType.EXPENSE),
            _AccountDef(code="5600", name="Marketing and Advertising", type=AccountType.EXPENSE),
            _AccountDef(code="5700", name="Insurance Expense", type=AccountType.EXPENSE),
            _AccountDef(code="5800", name="Depreciation Expense", type=AccountType.EXPENSE),
            _AccountDef(code="5900", name="Professional Fees", type=AccountType.EXPENSE),
            _AccountDef(code="5950", name="Miscellaneous Expense", type=AccountType.EXPENSE),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def seed_default_coa(session: Session, company_id: uuid.UUID) -> list[Account]:
    """Populate *company_id* with a standard chart of accounts.

    The function is **idempotent**: any account whose ``(company_id, code)``
    pair already exists is skipped.  The full list of :class:`Account` objects
    that were *created* during this call is returned.

    Args:
        session: An open SQLAlchemy :class:`~sqlalchemy.orm.Session`.
        company_id: UUID of the company to seed.

    Returns:
        A list of newly created :class:`Account` instances (empty if all
        accounts already existed).
    """
    # Fetch existing codes so we can skip duplicates.
    from sqlalchemy import select

    existing_codes: set[str] = set(
        session.scalars(select(Account.code).where(Account.company_id == company_id)).all()
    )

    created: list[Account] = []

    def _create(
        definition: _AccountDef,
        parent_id: uuid.UUID | None,
    ) -> Account | None:
        """Recursively create an account and its children."""
        if definition.code in existing_codes:
            # Account exists – resolve its DB id so children can reference it.
            existing: Account | None = session.scalars(
                select(Account).where(
                    Account.company_id == company_id,
                    Account.code == definition.code,
                )
            ).first()
            acct_id = existing.id if existing else None
        else:
            acct = Account(
                id=uuid.uuid4(),
                company_id=company_id,
                parent_id=parent_id,
                code=definition.code,
                name=definition.name,
                type=definition.type,
                normal_balance=definition.resolved_normal_balance(),
                description=definition.description,
            )
            session.add(acct)
            session.flush()  # obtain DB-generated id before children reference it
            existing_codes.add(definition.code)
            created.append(acct)
            acct_id = acct.id

        for child_def in definition.children:
            _create(child_def, parent_id=acct_id)

        return None

    for root_def in _SEED:
        _create(root_def, parent_id=None)

    return created


# ---------------------------------------------------------------------------
# Convenience: flat list of all (code, name, type) in seed order
# ---------------------------------------------------------------------------


def _flatten_seed(
    nodes: list[_AccountDef],
    parent_code: str | None = None,
) -> list[dict[str, Any]]:
    """Return a flat list of seed entries (used in tests / introspection)."""
    result: list[dict[str, Any]] = []
    for node in nodes:
        result.append(
            {
                "code": node.code,
                "name": node.name,
                "type": node.type,
                "parent_code": parent_code,
            }
        )
        result.extend(_flatten_seed(node.children, parent_code=node.code))
    return result


DEFAULT_COA_ENTRIES: list[dict[str, Any]] = _flatten_seed(_SEED)
