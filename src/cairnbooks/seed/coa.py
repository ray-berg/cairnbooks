"""Default Chart of Accounts seed data.

Provides a minimal but complete COA for a typical small business,
structured in five sections following GAAP conventions:

    1000–1999   Assets
    2000–2999   Liabilities
    3000–3999   Equity
    4000–4999   Income (Revenue)
    5000–5999   Expenses

Usage
-----
::

    from cairnbooks.seed.coa import default_coa_entries
    entries = default_coa_entries(company_id=your_company_uuid)
    # Insert via: session.execute(insert(Account), entries)

Ordering guarantee
------------------
The returned list is ordered so that every parent account appears
**before** its children.  Bulk-inserting the list in order therefore
satisfies the ``fk_accounts_parent_id`` foreign-key constraint without
deferred constraint handling.

Idempotency
-----------
Account ``id`` values are deterministic (UUID5 keyed on the account
code and a fixed namespace).  Re-running the seed with
``INSERT … ON CONFLICT DO NOTHING`` is safe and produces no duplicates.
"""

from __future__ import annotations

import uuid
from typing import Any

from cairnbooks.models.account import AccountType

# ---------------------------------------------------------------------------
# Deterministic UUID namespace — all seed UUIDs derive from this.
# Change this value only if you need to invalidate all seed IDs.
# ---------------------------------------------------------------------------
_COA_NAMESPACE = uuid.UUID("7c9e6679-7425-40de-944b-e07fc1f90ae7")


def _seed_uuid(code: str) -> uuid.UUID:
    """Return a deterministic UUID for the seed account identified by *code*."""
    return uuid.uuid5(_COA_NAMESPACE, f"cairnbooks.coa.account.{code}")


# ---------------------------------------------------------------------------
# COA definition
# Each tuple: (code, name, AccountType, parent_code | None)
# MUST be ordered: parents before children.
# ---------------------------------------------------------------------------
_COA: list[tuple[str, str, AccountType, str | None]] = [
    # ── ASSETS (1000–1999) ───────────────────────────────────────────────
    ("1000", "Current Assets",              AccountType.ASSET,     None),
    ("1010", "Cash and Cash Equivalents",   AccountType.ASSET,     "1000"),
    ("1011", "Petty Cash",                  AccountType.ASSET,     "1010"),
    ("1012", "Checking Account",            AccountType.ASSET,     "1010"),
    ("1013", "Savings Account",             AccountType.ASSET,     "1010"),
    ("1020", "Accounts Receivable",         AccountType.ASSET,     "1000"),
    ("1030", "Inventory",                   AccountType.ASSET,     "1000"),
    ("1040", "Prepaid Expenses",            AccountType.ASSET,     "1000"),
    ("1050", "Other Current Assets",        AccountType.ASSET,     "1000"),
    ("1100", "Non-Current Assets",          AccountType.ASSET,     None),
    ("1110", "Property, Plant & Equipment", AccountType.ASSET,     "1100"),
    ("1111", "Equipment",                   AccountType.ASSET,     "1110"),
    ("1112", "Vehicles",                    AccountType.ASSET,     "1110"),
    ("1113", "Furniture and Fixtures",      AccountType.ASSET,     "1110"),
    ("1120", "Accumulated Depreciation",    AccountType.ASSET,     "1100"),
    ("1130", "Intangible Assets",           AccountType.ASSET,     "1100"),
    ("1140", "Long-Term Investments",       AccountType.ASSET,     "1100"),
    # ── LIABILITIES (2000–2999) ──────────────────────────────────────────
    ("2000", "Current Liabilities",         AccountType.LIABILITY, None),
    ("2010", "Accounts Payable",            AccountType.LIABILITY, "2000"),
    ("2020", "Accrued Liabilities",         AccountType.LIABILITY, "2000"),
    ("2030", "Sales Tax Payable",           AccountType.LIABILITY, "2000"),
    ("2040", "Payroll Liabilities",         AccountType.LIABILITY, "2000"),
    ("2050", "Short-Term Loans Payable",    AccountType.LIABILITY, "2000"),
    ("2060", "Unearned Revenue",            AccountType.LIABILITY, "2000"),
    ("2070", "Other Current Liabilities",   AccountType.LIABILITY, "2000"),
    ("2100", "Non-Current Liabilities",     AccountType.LIABILITY, None),
    ("2110", "Long-Term Loans Payable",     AccountType.LIABILITY, "2100"),
    ("2120", "Deferred Tax Liability",      AccountType.LIABILITY, "2100"),
    ("2130", "Other Long-Term Liabilities", AccountType.LIABILITY, "2100"),
    # ── EQUITY (3000–3999) ───────────────────────────────────────────────
    ("3000", "Owner's Equity",                      AccountType.EQUITY, None),
    ("3010", "Common Stock / Capital Contributed",  AccountType.EQUITY, "3000"),
    ("3020", "Retained Earnings",                   AccountType.EQUITY, "3000"),
    ("3030", "Owner's Draws / Distributions",       AccountType.EQUITY, "3000"),
    ("3040", "Current Year Earnings",               AccountType.EQUITY, "3000"),
    # ── INCOME (4000–4999) ───────────────────────────────────────────────
    ("4000", "Revenue",                     AccountType.INCOME,    None),
    ("4010", "Sales Revenue",               AccountType.INCOME,    "4000"),
    ("4020", "Service Revenue",             AccountType.INCOME,    "4000"),
    ("4030", "Other Operating Income",      AccountType.INCOME,    "4000"),
    ("4040", "Interest Income",             AccountType.INCOME,    "4000"),
    ("4050", "Other Non-Operating Income",  AccountType.INCOME,    "4000"),
    # ── EXPENSES (5000–5999) ─────────────────────────────────────────────
    ("5000", "Operating Expenses",                    AccountType.EXPENSE, None),
    ("5010", "Cost of Goods Sold",                    AccountType.EXPENSE, "5000"),
    ("5020", "Salaries and Wages",                    AccountType.EXPENSE, "5000"),
    ("5030", "Payroll Tax Expense",                   AccountType.EXPENSE, "5000"),
    ("5040", "Rent Expense",                          AccountType.EXPENSE, "5000"),
    ("5050", "Utilities Expense",                     AccountType.EXPENSE, "5000"),
    ("5060", "Office Supplies Expense",               AccountType.EXPENSE, "5000"),
    ("5070", "Insurance Expense",                     AccountType.EXPENSE, "5000"),
    ("5080", "Depreciation Expense",                  AccountType.EXPENSE, "5000"),
    ("5090", "Advertising and Marketing Expense",     AccountType.EXPENSE, "5000"),
    ("5100", "Professional Services Expense",         AccountType.EXPENSE, "5000"),
    ("5110", "Travel and Entertainment Expense",      AccountType.EXPENSE, "5000"),
    ("5120", "Repairs and Maintenance Expense",       AccountType.EXPENSE, "5000"),
    ("5130", "Bank Charges and Fees",                 AccountType.EXPENSE, "5000"),
    ("5140", "Interest Expense",                      AccountType.EXPENSE, "5000"),
    ("5150", "Income Tax Expense",                    AccountType.EXPENSE, "5000"),
    ("5160", "Miscellaneous Expense",                 AccountType.EXPENSE, "5000"),
]


def default_coa_entries(company_id: uuid.UUID | str) -> list[dict[str, Any]]:
    """Return the default Chart of Accounts as ordered row dicts.

    Each dict contains all columns needed to insert a row into the
    ``accounts`` table:  ``id``, ``company_id``, ``code``, ``name``,
    ``type``, ``parent_id``, ``active``.

    The list is **insert-ordered**: every parent appears before its
    children, so a sequential bulk-insert satisfies the
    ``fk_accounts_parent_id`` foreign-key constraint.

    Args:
        company_id: UUID of the owning company.  Accepts either a
            :class:`uuid.UUID` or its string representation.

    Returns:
        Ordered list of account row dicts.

    Example::

        from sqlalchemy import insert
        from cairnbooks.models.account import Account
        from cairnbooks.seed.coa import default_coa_entries

        entries = default_coa_entries(company.id)
        await session.execute(insert(Account).prefix_with("OR IGNORE"), entries)
        # PostgreSQL: use ON CONFLICT DO NOTHING
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(Account).on_conflict_do_nothing(index_elements=["company_id", "code"])
        await session.execute(stmt, entries)
    """
    cid = str(company_id)
    rows: list[dict[str, Any]] = []
    for code, name, acct_type, parent_code in _COA:
        rows.append(
            {
                "id": str(_seed_uuid(code)),
                "company_id": cid,
                "code": code,
                "name": name,
                "type": acct_type.value,
                "parent_id": str(_seed_uuid(parent_code)) if parent_code else None,
                "active": True,
            }
        )
    return rows
