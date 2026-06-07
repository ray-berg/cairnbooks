"""Trial Balance report — per-account debit/credit totals as-of a given date.

Overview
--------
A **Trial Balance** is a fundamental accounting report that lists every account
with a non-zero balance, together with its total debits and total credits, as of
a particular date.  The grand-total row at the bottom must satisfy the
double-entry invariant:

    sum(total_debits) == sum(total_credits)

This module provides:

* :class:`TrialBalanceLine`  – one row per account (Pydantic model).
* :class:`TrialBalanceReport` – full report with lines and grand totals (Pydantic).
* :func:`compute_trial_balance` – async function that queries the DB and returns
  a :class:`TrialBalanceReport`.

Query strategy
--------------
Only **posted** journal lines are included; draft journals are excluded.
Lines are aggregated up to and including *as_of* (``journals.date <= as_of``).
Accounts with no posted activity are omitted (they appear with zero balance
on the balance sheet, not the trial balance).

The SQL executed is equivalent to::

    SELECT
        a.id,
        a.code,
        a.name,
        a.type,
        COALESCE(SUM(jl.debit),  0) AS total_debit,
        COALESCE(SUM(jl.credit), 0) AS total_credit
    FROM   accounts a
    JOIN   journal_lines jl ON jl.account_id = a.id
    JOIN   journals j        ON j.id = jl.journal_id
    WHERE  j.company_id = :company_id
      AND  j.status     = 'posted'
      AND  j.date      <= :as_of
    GROUP  BY a.id, a.code, a.name, a.type
    ORDER  BY a.code;
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cairnbooks.models.account import Account
from cairnbooks.models.journal import Journal, JournalLine, JournalStatus

__all__ = [
    "TrialBalanceLine",
    "TrialBalanceReport",
    "compute_trial_balance",
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrialBalanceLine:
    """One row in the trial balance report — one account.

    Attributes
    ----------
    account_id:
        UUID of the :class:`~cairnbooks.models.account.Account`.
    code:
        Short account code (e.g. ``"1010"``).
    name:
        Human-readable account name (e.g. ``"Checking Account"``).
    account_type:
        One of ``asset | liability | equity | income | expense``.
    total_debit:
        Sum of all posted debit amounts on this account up to and including
        the as-of date.  Never negative.
    total_credit:
        Sum of all posted credit amounts on this account up to and including
        the as-of date.  Never negative.
    """

    account_id: uuid.UUID
    code: str
    name: str
    account_type: str
    total_debit: Decimal
    total_credit: Decimal


@dataclass(frozen=True)
class TrialBalanceReport:
    """Full trial balance report.

    Attributes
    ----------
    company_id:
        The company this report belongs to.
    as_of:
        The report date (inclusive upper bound for journal dates).
    lines:
        Per-account rows, ordered by account code.
    grand_total_debit:
        Sum of :attr:`TrialBalanceLine.total_debit` across all lines.
    grand_total_credit:
        Sum of :attr:`TrialBalanceLine.total_credit` across all lines.
    is_balanced:
        ``True`` when :attr:`grand_total_debit` == :attr:`grand_total_credit`.
        This should always be ``True`` for a correct ledger.
    """

    company_id: uuid.UUID
    as_of: date
    lines: list[TrialBalanceLine] = field(default_factory=list)
    grand_total_debit: Decimal = Decimal("0")
    grand_total_credit: Decimal = Decimal("0")

    @property
    def is_balanced(self) -> bool:
        """Return ``True`` when total debits equal total credits."""
        return self.grand_total_debit == self.grand_total_credit


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


async def compute_trial_balance(
    session: AsyncSession,
    company_id: uuid.UUID,
    as_of: date,
) -> TrialBalanceReport:
    """Query the database and return a :class:`TrialBalanceReport`.

    Parameters
    ----------
    session:
        Active :class:`~sqlalchemy.ext.asyncio.AsyncSession`.
    company_id:
        Filter journals and accounts to this company.
    as_of:
        Upper bound for journal dates (inclusive).  Only posted journals
        with ``date <= as_of`` are included.

    Returns
    -------
    TrialBalanceReport
        Report object with per-account lines and grand totals.
        :attr:`~TrialBalanceReport.is_balanced` will be ``True`` for any
        correctly double-entry ledger.
    """
    # ------------------------------------------------------------------
    # Build query
    # ------------------------------------------------------------------
    # Aggregate debit and credit per account, restricted to:
    #   - company_id scope on the journal
    #   - posted status
    #   - date on or before as_of
    stmt = (
        select(
            Account.id.label("account_id"),
            Account.code.label("code"),
            Account.name.label("name"),
            Account.type.label("account_type"),
            func.coalesce(func.sum(JournalLine.debit), Decimal("0")).label("total_debit"),
            func.coalesce(func.sum(JournalLine.credit), Decimal("0")).label("total_credit"),
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(Journal, Journal.id == JournalLine.journal_id)
        .where(
            Journal.company_id == company_id,
            Journal.status == JournalStatus.POSTED,
            Journal.date <= as_of,
        )
        .group_by(Account.id, Account.code, Account.name, Account.type)
        .order_by(Account.code)
    )

    result = await session.execute(stmt)
    rows = result.all()

    # ------------------------------------------------------------------
    # Map rows → TrialBalanceLine objects
    # ------------------------------------------------------------------
    lines: list[TrialBalanceLine] = [
        TrialBalanceLine(
            account_id=row.account_id,
            code=row.code,
            name=row.name,
            account_type=row.account_type,
            total_debit=Decimal(str(row.total_debit)),
            total_credit=Decimal(str(row.total_credit)),
        )
        for row in rows
    ]

    # ------------------------------------------------------------------
    # Grand totals
    # ------------------------------------------------------------------
    grand_total_debit: Decimal = sum(
        (ln.total_debit for ln in lines), Decimal("0")
    )
    grand_total_credit: Decimal = sum(
        (ln.total_credit for ln in lines), Decimal("0")
    )

    return TrialBalanceReport(
        company_id=company_id,
        as_of=as_of,
        lines=lines,
        grand_total_debit=grand_total_debit,
        grand_total_credit=grand_total_credit,
    )
