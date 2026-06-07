"""Posting engine: balanced debit/credit invariant enforcement.

Public API
----------
post_journal(session, journal, entries)
    Validates that ``sum(debits) == sum(credits)`` across *entries*, then
    marks *journal* as ``posted`` and flushes all objects within the caller's
    database transaction (atomic).

Design
------
The balance check is performed first, before any state is mutated, so a
failed validation leaves the journal and entries untouched.  The SQLAlchemy
session flush is deferred to the end: the caller owns ``commit`` / ``rollback``
(typically via the :func:`~cairnbooks.db.get_db` FastAPI dependency), which
guarantees atomicity — if anything after the flush fails before ``commit``, the
database rolls back automatically.

Raises
------
JournalImbalancedError
    When ``sum(debits) != sum(credits)``.
JournalPostedError
    When the journal is already in ``posted`` status.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from cairnbooks.models.journal import (
    Journal,
    JournalImbalancedError,
    JournalLine,
)

__all__ = ["post_journal"]


def _check_balance(entries: Sequence[JournalLine]) -> None:
    """Raise :class:`JournalImbalancedError` when debits ≠ credits.

    Parameters
    ----------
    entries:
        Sequence of :class:`~cairnbooks.models.journal.JournalLine` objects
        representing all legs of the proposed posting.

    Raises
    ------
    JournalImbalancedError
        When the sum of :attr:`~JournalLine.debit` values does not equal the
        sum of :attr:`~JournalLine.credit` values across *entries*.
    """
    total_debit: Decimal = sum((e.debit for e in entries), Decimal("0"))
    total_credit: Decimal = sum((e.credit for e in entries), Decimal("0"))
    if total_debit != total_credit:
        raise JournalImbalancedError(
            f"Journal is not balanced: "
            f"sum(debits)={total_debit} != sum(credits)={total_credit}."
        )


async def post_journal(
    session: AsyncSession,
    journal: Journal,
    entries: Sequence[JournalLine],
) -> Journal:
    """Validate balance and atomically post a double-entry journal.

    Steps
    -----
    1. **Balance check** — raises immediately if ``sum(debits) != sum(credits)``;
       no state is mutated before this passes.
    2. **Status transition** — calls :meth:`Journal.post()` to move the journal
       from ``draft`` → ``posted`` (raises :class:`JournalPostedError` if it is
       already posted).
    3. **Session registration** — adds the journal and every line to *session*.
    4. **Flush** — writes all pending changes to the database within the
       caller's transaction; the caller must ``commit`` to make them permanent
       or ``rollback`` to discard them.

    Parameters
    ----------
    session:
        Active :class:`~sqlalchemy.ext.asyncio.AsyncSession`.  The caller is
        responsible for ``commit`` / ``rollback``.
    journal:
        A :class:`~cairnbooks.models.journal.Journal` in ``draft`` status.
    entries:
        One or more :class:`~cairnbooks.models.journal.JournalLine` objects
        representing the legs of the posting.

    Returns
    -------
    Journal
        The same *journal* object, now in ``posted`` status.

    Raises
    ------
    JournalImbalancedError
        When ``sum(debits) != sum(credits)`` across *entries*.
    JournalPostedError
        When *journal* is already in ``posted`` status.
    """
    # 1. Validate balance — pure logic, no side effects.
    _check_balance(entries)

    # 2. Transition draft → posted (raises JournalPostedError if already posted).
    journal.post()

    # 3. Register all objects with the session.
    session.add(journal)
    for line in entries:
        session.add(line)

    # 4. Flush within the caller's transaction.
    await session.flush()

    return journal
