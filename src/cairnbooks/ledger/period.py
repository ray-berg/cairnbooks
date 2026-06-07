"""Period management: fiscal-period close and posting-date guard.

Public API
----------
close_period(session, period)
    Closes *period* (``open`` → ``closed``), registers it with the session,
    and flushes.  Raises if the period is already closed.

assert_open_for_date(periods, entry_date)
    Pure guard — raises :class:`~cairnbooks.models.period.FiscalPeriodClosedError`
    if *entry_date* falls inside any closed period in *periods*.

Design
------
The guard function is intentionally stateless and synchronous so it can be
called cheaply inside route handlers without an additional database round-trip.
The caller is expected to have already loaded the relevant
:class:`~cairnbooks.models.period.FiscalPeriod` rows for the company into
memory (e.g. by querying for all periods whose range covers the entry date).

The ``close_period`` service follows the same session-flush pattern as
:func:`cairnbooks.ledger.posting.post_journal`: the caller owns ``commit`` /
``rollback``, guaranteeing atomicity.

Raises
------
FiscalPeriodClosedError
    Raised by :func:`assert_open_for_date` when *entry_date* falls in a
    closed period.
FiscalPeriodAlreadyClosedError
    Raised by :func:`close_period` when the period is already closed.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from cairnbooks.models.period import (
    FiscalPeriod,
    FiscalPeriodClosedError,  # re-exported for callers' convenience
)

__all__ = [
    "assert_open_for_date",
    "close_period",
    "FiscalPeriodClosedError",
]


def assert_open_for_date(
    periods: Sequence[FiscalPeriod],
    entry_date: date,
) -> None:
    """Raise :class:`FiscalPeriodClosedError` if *entry_date* falls in any closed period.

    Iterates over every period in *periods* and delegates to
    :meth:`~cairnbooks.models.period.FiscalPeriod.assert_posting_allowed`.
    The first closed period that covers *entry_date* aborts the check.

    This function is **pure** — it performs no I/O and mutates nothing.
    Call it before creating or posting a journal entry to enforce the
    "no postings in a closed period" accounting invariant.

    Parameters
    ----------
    periods:
        Sequence of :class:`~cairnbooks.models.period.FiscalPeriod` objects
        to check.  Typically the caller filters these to the periods whose
        date range might overlap the entry date.
    entry_date:
        The accounting date of the proposed journal entry.

    Raises
    ------
    FiscalPeriodClosedError
        When *entry_date* falls within a closed period in *periods*.
    """
    for period in periods:
        period.assert_posting_allowed(entry_date)


async def close_period(
    session: AsyncSession,
    period: FiscalPeriod,
) -> FiscalPeriod:
    """Close a fiscal period and flush the change to the database.

    Steps
    -----
    1. **Status transition** — calls :meth:`~cairnbooks.models.period.FiscalPeriod.close`
       to move the period from ``open`` → ``closed`` (raises
       :class:`~cairnbooks.models.period.FiscalPeriodAlreadyClosedError` if
       already closed).
    2. **Session registration** — adds the modified period to *session*.
    3. **Flush** — writes the change within the caller's transaction;
       the caller must ``commit`` to make it permanent.

    Parameters
    ----------
    session:
        Active :class:`~sqlalchemy.ext.asyncio.AsyncSession`.  The caller is
        responsible for ``commit`` / ``rollback``.
    period:
        A :class:`~cairnbooks.models.period.FiscalPeriod` in ``open`` status.

    Returns
    -------
    FiscalPeriod
        The same *period* object, now in ``closed`` status.

    Raises
    ------
    FiscalPeriodAlreadyClosedError
        When *period* is already in ``closed`` status.
    """
    # 1. Transition open → closed (raises if already closed).
    period.close()

    # 2. Register with the session.
    session.add(period)

    # 3. Flush within the caller's transaction.
    await session.flush()

    return period
