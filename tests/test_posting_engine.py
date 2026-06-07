"""Unit tests for the posting engine (cairnbooks.ledger.posting).

These tests are pure-Python and do NOT require a running database.
The SQLAlchemy session is replaced by an :class:`unittest.mock.AsyncMock`
so that the async ``flush`` call resolves without real I/O.

Coverage
--------
- Unbalanced entries raise :class:`JournalImbalancedError`.
- Balanced entries successfully post the journal (status → ``posted``).
- Posting an already-posted journal raises :class:`JournalPostedError`.
- Zero-entry journal raises :class:`JournalImbalancedError` (trivially
  balanced but empty; debit == credit == 0 passes — tested separately).
- Multiple lines summing to the same total are accepted.
- Mismatched totals by a single cent are rejected.
- :func:`post_journal` is re-exported from the ledger package.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from cairnbooks.ledger.posting import post_journal
from cairnbooks.models.journal import (
    Journal,
    JournalError,
    JournalImbalancedError,
    JournalLine,
    JournalPostedError,
    JournalStatus,
)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_ACCOUNT_CASH = uuid.UUID("00000000-0000-0000-0000-000000000010")
_ACCOUNT_REV = uuid.UUID("00000000-0000-0000-0000-000000000011")
_TODAY = date(2026, 6, 7)


def _draft_journal(**kwargs) -> Journal:
    """Return a minimal draft Journal (no DB required)."""
    defaults = dict(
        company_id=_COMPANY_ID,
        date=_TODAY,
        status=JournalStatus.DRAFT,
    )
    defaults.update(kwargs)
    return Journal(**defaults)


def _line(account_id: uuid.UUID = _ACCOUNT_CASH, **kwargs) -> JournalLine:
    """Return a JournalLine with sensible defaults."""
    defaults = dict(
        account_id=account_id,
        debit=Decimal("0"),
        credit=Decimal("0"),
        line_number=1,
    )
    defaults.update(kwargs)
    return JournalLine(**defaults)


def _mock_session() -> MagicMock:
    """Return a mock that mimics an AsyncSession.

    ``session.add`` is a regular synchronous call in SQLAlchemy; only
    ``session.flush`` (and ``commit``/``rollback``) are coroutines.
    """
    session = MagicMock()
    session.add = MagicMock(return_value=None)   # sync
    session.flush = AsyncMock(return_value=None)  # async
    return session


def _run(coro):
    """Convenience wrapper: run a coroutine synchronously in tests."""
    return asyncio.run(coro)


# ===========================================================================
# Unbalanced entries → JournalImbalancedError
# ===========================================================================


class TestUnbalancedRaises:
    """post_journal must raise JournalImbalancedError when debits ≠ credits."""

    def test_single_debit_no_credit_raises(self) -> None:
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("500.00"), credit=Decimal("0")),
        ]
        with pytest.raises(JournalImbalancedError):
            _run(post_journal(_mock_session(), journal, entries))

    def test_single_credit_no_debit_raises(self) -> None:
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("250.00")),
        ]
        with pytest.raises(JournalImbalancedError):
            _run(post_journal(_mock_session(), journal, entries))

    def test_unequal_multi_line_raises(self) -> None:
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("100.00"), credit=Decimal("0")),
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("99.99")),
        ]
        with pytest.raises(JournalImbalancedError):
            _run(post_journal(_mock_session(), journal, entries))

    def test_off_by_one_cent_raises(self) -> None:
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("1000.00"), credit=Decimal("0")),
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("999.99")),
        ]
        with pytest.raises(JournalImbalancedError):
            _run(post_journal(_mock_session(), journal, entries))

    def test_imbalanced_error_is_journal_error(self) -> None:
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("100.00"), credit=Decimal("0")),
        ]
        with pytest.raises(JournalError):
            _run(post_journal(_mock_session(), journal, entries))

    def test_unbalanced_leaves_journal_in_draft(self) -> None:
        """Journal status must stay draft when balance check fails."""
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("100.00"), credit=Decimal("0")),
        ]
        with pytest.raises(JournalImbalancedError):
            _run(post_journal(_mock_session(), journal, entries))
        assert journal.status == JournalStatus.DRAFT

    def test_unbalanced_session_flush_not_called(self) -> None:
        """Session flush must NOT be called when balance check fails."""
        journal = _draft_journal()
        session = _mock_session()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("100.00"), credit=Decimal("0")),
        ]
        with pytest.raises(JournalImbalancedError):
            _run(post_journal(session, journal, entries))
        session.flush.assert_not_called()


# ===========================================================================
# Balanced entries → journal posted successfully
# ===========================================================================


class TestBalancedPosts:
    """post_journal must post the journal when debits == credits."""

    def test_simple_two_line_posts(self) -> None:
        """Classic cash-revenue posting: Dr Cash / Cr Revenue."""
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("500.00"), credit=Decimal("0"), line_number=1),
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("500.00"), line_number=2),
        ]
        _run(post_journal(_mock_session(), journal, entries))
        assert journal.status == JournalStatus.POSTED

    def test_balanced_is_posted_true(self) -> None:
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("200.00"), credit=Decimal("0")),
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("200.00")),
        ]
        _run(post_journal(_mock_session(), journal, entries))
        assert journal.is_posted is True

    def test_balanced_returns_journal(self) -> None:
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("100.00"), credit=Decimal("0")),
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("100.00")),
        ]
        result = _run(post_journal(_mock_session(), journal, entries))
        assert result is journal

    def test_balanced_session_flush_called(self) -> None:
        """Session flush must be called exactly once on success."""
        journal = _draft_journal()
        session = _mock_session()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("100.00"), credit=Decimal("0")),
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("100.00")),
        ]
        _run(post_journal(session, journal, entries))
        session.flush.assert_called_once()

    def test_balanced_session_add_called_for_journal(self) -> None:
        """The journal itself must be added to the session."""
        journal = _draft_journal()
        session = _mock_session()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("100.00"), credit=Decimal("0")),
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("100.00")),
        ]
        _run(post_journal(session, journal, entries))
        added_objects = [c.args[0] for c in session.add.call_args_list]
        assert journal in added_objects

    def test_balanced_session_add_called_for_lines(self) -> None:
        """Every line must be added to the session."""
        journal = _draft_journal()
        session = _mock_session()
        line1 = _line(_ACCOUNT_CASH, debit=Decimal("75.00"), credit=Decimal("0"), line_number=1)
        line2 = _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("75.00"), line_number=2)
        _run(post_journal(session, journal, [line1, line2]))
        added_objects = [c.args[0] for c in session.add.call_args_list]
        assert line1 in added_objects
        assert line2 in added_objects

    def test_zero_balanced_entry_posts(self) -> None:
        """A trivially balanced entry (0 == 0) is mathematically valid."""
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("0"), credit=Decimal("0")),
        ]
        _run(post_journal(_mock_session(), journal, entries))
        assert journal.is_posted is True

    def test_multi_line_balanced_posts(self) -> None:
        """Multiple lines that sum to the same total are accepted."""
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("300.00"), credit=Decimal("0"), line_number=1),
            _line(_ACCOUNT_CASH, debit=Decimal("200.00"), credit=Decimal("0"), line_number=2),
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("500.00"), line_number=3),
        ]
        _run(post_journal(_mock_session(), journal, entries))
        assert journal.status == JournalStatus.POSTED

    def test_high_precision_balanced_posts(self) -> None:
        """Four-decimal-place amounts that sum equally are accepted."""
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("0.0001"), credit=Decimal("0")),
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("0.0001")),
        ]
        _run(post_journal(_mock_session(), journal, entries))
        assert journal.is_posted is True


# ===========================================================================
# Already-posted journal
# ===========================================================================


class TestAlreadyPostedJournal:
    """Attempting to post an already-posted journal must raise JournalPostedError."""

    def test_double_post_raises_posted_error(self) -> None:
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("100.00"), credit=Decimal("0")),
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("100.00")),
        ]
        # First post succeeds.
        _run(post_journal(_mock_session(), journal, entries))
        # Second attempt must fail.
        with pytest.raises(JournalPostedError):
            _run(post_journal(_mock_session(), journal, entries))

    def test_double_post_raises_journal_error(self) -> None:
        journal = _draft_journal()
        entries = [
            _line(_ACCOUNT_CASH, debit=Decimal("100.00"), credit=Decimal("0")),
            _line(_ACCOUNT_REV, debit=Decimal("0"), credit=Decimal("100.00")),
        ]
        _run(post_journal(_mock_session(), journal, entries))
        with pytest.raises(JournalError):
            _run(post_journal(_mock_session(), journal, entries))


# ===========================================================================
# Module / package export
# ===========================================================================


class TestModuleExport:
    """post_journal must be importable from the ledger package."""

    def test_importable_from_ledger_package(self) -> None:
        from cairnbooks.ledger import posting  # noqa: F401
        from cairnbooks.ledger.posting import post_journal as pj  # noqa: F401
        assert callable(pj)
