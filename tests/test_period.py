"""Unit tests for FiscalPeriod model and the period ledger service.

These tests are pure-Python and do NOT require a running database.
The SQLAlchemy session is replaced by an :class:`unittest.mock.AsyncMock`
so that the async ``flush`` call resolves without real I/O.

Coverage
--------
Model — FiscalPeriod
  - New period starts open.
  - ``is_open`` / ``is_closed`` reflect status correctly.
  - ``contains_date`` boundary conditions (before, first, inside, last, after).
  - ``assert_posting_allowed`` allows any date when period is open.
  - ``assert_posting_allowed`` raises FiscalPeriodClosedError for in-range dates
    when period is closed.
  - ``assert_posting_allowed`` does NOT raise for out-of-range dates even when
    period is closed.
  - ``close()`` transitions status to closed and records ``closed_at``.
  - ``close()`` on already-closed period raises FiscalPeriodAlreadyClosedError.
  - FiscalPeriodClosedError and FiscalPeriodAlreadyClosedError are both
    FiscalPeriodError subclasses.

Service — ledger.period
  - ``assert_open_for_date`` with empty sequence is a no-op.
  - ``assert_open_for_date`` with all-open periods is a no-op.
  - ``assert_open_for_date`` raises when any closed period covers the date.
  - ``assert_open_for_date`` does not raise when closed period does NOT cover date.
  - Multiple periods: raises on the first matching closed period.
  - ``close_period`` closes the period, adds it to the session, and flushes.
  - ``close_period`` propagates FiscalPeriodAlreadyClosedError unchanged.
  - ``close_period`` is importable from ledger package.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from cairnbooks.ledger.period import assert_open_for_date, close_period
from cairnbooks.models.period import (
    FiscalPeriod,
    FiscalPeriodAlreadyClosedError,
    FiscalPeriodClosedError,
    FiscalPeriodError,
    PeriodStatus,
)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# A canonical Q1-2026 period used across most tests.
_Q1_START = date(2026, 1, 1)
_Q1_END = date(2026, 3, 31)

# Dates used in tests
_BEFORE_Q1 = date(2025, 12, 31)
_FIRST_DAY = date(2026, 1, 1)
_MID_Q1 = date(2026, 2, 15)
_LAST_DAY = date(2026, 3, 31)
_AFTER_Q1 = date(2026, 4, 1)


def _open_period(**kwargs) -> FiscalPeriod:
    """Return a minimal open FiscalPeriod (no DB required)."""
    defaults = dict(
        company_id=_COMPANY_ID,
        name="2026-Q1",
        start_date=_Q1_START,
        end_date=_Q1_END,
        status=PeriodStatus.OPEN,
    )
    defaults.update(kwargs)
    return FiscalPeriod(**defaults)


def _closed_period(**kwargs) -> FiscalPeriod:
    """Return a FiscalPeriod already in closed status."""
    period = _open_period(**kwargs)
    period.status = PeriodStatus.CLOSED
    return period


def _mock_session() -> MagicMock:
    """Return a mock that mimics an AsyncSession.

    ``session.add`` is synchronous; ``session.flush`` is a coroutine.
    """
    session = MagicMock()
    session.add = MagicMock(return_value=None)
    session.flush = AsyncMock(return_value=None)
    return session


def _run(coro):
    """Run a coroutine synchronously in tests."""
    return asyncio.run(coro)


# ===========================================================================
# FiscalPeriod — initial state
# ===========================================================================


class TestInitialState:
    """A freshly created FiscalPeriod must start in the open status."""

    def test_default_status_is_open(self) -> None:
        period = _open_period()
        assert period.status == PeriodStatus.OPEN

    def test_is_open_true_for_new_period(self) -> None:
        period = _open_period()
        assert period.is_open is True

    def test_is_closed_false_for_new_period(self) -> None:
        period = _open_period()
        assert period.is_closed is False

    def test_closed_at_is_none_for_open_period(self) -> None:
        period = _open_period()
        assert period.closed_at is None


# ===========================================================================
# FiscalPeriod.contains_date — boundary conditions
# ===========================================================================


class TestContainsDate:
    """contains_date must correctly identify whether a date falls in the range."""

    def test_date_before_range_is_false(self) -> None:
        period = _open_period()
        assert period.contains_date(_BEFORE_Q1) is False

    def test_first_day_is_true(self) -> None:
        period = _open_period()
        assert period.contains_date(_FIRST_DAY) is True

    def test_mid_range_is_true(self) -> None:
        period = _open_period()
        assert period.contains_date(_MID_Q1) is True

    def test_last_day_is_true(self) -> None:
        period = _open_period()
        assert period.contains_date(_LAST_DAY) is True

    def test_date_after_range_is_false(self) -> None:
        period = _open_period()
        assert period.contains_date(_AFTER_Q1) is False

    def test_single_day_period_contains_its_own_date(self) -> None:
        d = date(2026, 6, 15)
        period = _open_period(start_date=d, end_date=d)
        assert period.contains_date(d) is True

    def test_single_day_period_excludes_adjacent_days(self) -> None:
        d = date(2026, 6, 15)
        period = _open_period(start_date=d, end_date=d)
        assert period.contains_date(date(2026, 6, 14)) is False
        assert period.contains_date(date(2026, 6, 16)) is False


# ===========================================================================
# FiscalPeriod.assert_posting_allowed — open period
# ===========================================================================


class TestAssertPostingAllowedOpenPeriod:
    """assert_posting_allowed must be a no-op for any date when period is open."""

    def test_in_range_date_allowed_when_open(self) -> None:
        period = _open_period()
        period.assert_posting_allowed(_MID_Q1)  # must not raise

    def test_first_day_allowed_when_open(self) -> None:
        period = _open_period()
        period.assert_posting_allowed(_FIRST_DAY)

    def test_last_day_allowed_when_open(self) -> None:
        period = _open_period()
        period.assert_posting_allowed(_LAST_DAY)

    def test_out_of_range_date_allowed_when_open(self) -> None:
        period = _open_period()
        period.assert_posting_allowed(_BEFORE_Q1)
        period.assert_posting_allowed(_AFTER_Q1)


# ===========================================================================
# FiscalPeriod.assert_posting_allowed — closed period
# ===========================================================================


class TestAssertPostingAllowedClosedPeriod:
    """assert_posting_allowed must raise FiscalPeriodClosedError for in-range dates."""

    def test_in_range_raises_when_closed(self) -> None:
        period = _closed_period()
        with pytest.raises(FiscalPeriodClosedError):
            period.assert_posting_allowed(_MID_Q1)

    def test_first_day_raises_when_closed(self) -> None:
        period = _closed_period()
        with pytest.raises(FiscalPeriodClosedError):
            period.assert_posting_allowed(_FIRST_DAY)

    def test_last_day_raises_when_closed(self) -> None:
        period = _closed_period()
        with pytest.raises(FiscalPeriodClosedError):
            period.assert_posting_allowed(_LAST_DAY)

    def test_closed_error_is_fiscal_period_error(self) -> None:
        period = _closed_period()
        with pytest.raises(FiscalPeriodError):
            period.assert_posting_allowed(_MID_Q1)

    def test_before_range_allowed_when_closed(self) -> None:
        """Dates outside the period's range are never blocked."""
        period = _closed_period()
        period.assert_posting_allowed(_BEFORE_Q1)  # must not raise

    def test_after_range_allowed_when_closed(self) -> None:
        period = _closed_period()
        period.assert_posting_allowed(_AFTER_Q1)  # must not raise

    def test_error_message_contains_period_name(self) -> None:
        period = _closed_period(name="2026-Q1")
        with pytest.raises(FiscalPeriodClosedError, match="2026-Q1"):
            period.assert_posting_allowed(_MID_Q1)

    def test_error_message_contains_entry_date(self) -> None:
        period = _closed_period()
        with pytest.raises(FiscalPeriodClosedError, match=str(_MID_Q1)):
            period.assert_posting_allowed(_MID_Q1)


# ===========================================================================
# FiscalPeriod.close — lifecycle transition
# ===========================================================================


class TestClose:
    """close() must transition status and record closed_at."""

    def test_close_sets_status_to_closed(self) -> None:
        period = _open_period()
        period.close()
        assert period.status == PeriodStatus.CLOSED

    def test_close_sets_is_closed_true(self) -> None:
        period = _open_period()
        period.close()
        assert period.is_closed is True

    def test_close_sets_is_open_false(self) -> None:
        period = _open_period()
        period.close()
        assert period.is_open is False

    def test_close_records_closed_at(self) -> None:
        period = _open_period()
        period.close()
        assert period.closed_at is not None

    def test_close_closed_at_is_timezone_aware(self) -> None:
        period = _open_period()
        period.close()
        assert period.closed_at is not None
        assert period.closed_at.tzinfo is not None

    def test_double_close_raises_already_closed_error(self) -> None:
        period = _open_period()
        period.close()
        with pytest.raises(FiscalPeriodAlreadyClosedError):
            period.close()

    def test_already_closed_error_is_fiscal_period_error(self) -> None:
        period = _open_period()
        period.close()
        with pytest.raises(FiscalPeriodError):
            period.close()

    def test_already_closed_error_message_contains_name(self) -> None:
        period = _open_period(name="January 2026")
        period.close()
        with pytest.raises(FiscalPeriodAlreadyClosedError, match="January 2026"):
            period.close()

    def test_close_then_posting_blocked(self) -> None:
        """After close(), assert_posting_allowed must block in-range entries."""
        period = _open_period()
        period.assert_posting_allowed(_MID_Q1)  # allowed before close
        period.close()
        with pytest.raises(FiscalPeriodClosedError):
            period.assert_posting_allowed(_MID_Q1)  # blocked after close


# ===========================================================================
# Exception hierarchy
# ===========================================================================


class TestExceptionHierarchy:
    """Both concrete exceptions must be subclasses of FiscalPeriodError."""

    def test_closed_error_is_subclass_of_base(self) -> None:
        assert issubclass(FiscalPeriodClosedError, FiscalPeriodError)

    def test_already_closed_error_is_subclass_of_base(self) -> None:
        assert issubclass(FiscalPeriodAlreadyClosedError, FiscalPeriodError)


# ===========================================================================
# Service — assert_open_for_date
# ===========================================================================


class TestAssertOpenForDate:
    """assert_open_for_date must raise when any closed period covers the date."""

    def test_empty_sequence_is_noop(self) -> None:
        assert_open_for_date([], _MID_Q1)  # must not raise

    def test_all_open_periods_is_noop(self) -> None:
        periods = [_open_period(), _open_period(name="2026-Q2")]
        assert_open_for_date(periods, _MID_Q1)

    def test_single_closed_period_in_range_raises(self) -> None:
        periods = [_closed_period()]
        with pytest.raises(FiscalPeriodClosedError):
            assert_open_for_date(periods, _MID_Q1)

    def test_single_closed_period_out_of_range_is_noop(self) -> None:
        periods = [_closed_period()]
        assert_open_for_date(periods, _AFTER_Q1)  # must not raise

    def test_mixed_open_closed_raises_on_closed(self) -> None:
        """Even when one period is open, a closed period covering the date raises."""
        open_p = _open_period()
        closed_p = _closed_period(name="2026-Q1-duplicate")
        with pytest.raises(FiscalPeriodClosedError):
            assert_open_for_date([open_p, closed_p], _MID_Q1)

    def test_two_closed_periods_different_ranges(self) -> None:
        """Date in range of second closed period raises correctly."""
        closed_q1 = _closed_period(name="2026-Q1")
        closed_q2 = _closed_period(
            name="2026-Q2",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 6, 30),
        )
        # Q1 date blocked by first period
        with pytest.raises(FiscalPeriodClosedError):
            assert_open_for_date([closed_q1, closed_q2], _MID_Q1)
        # Q2 date blocked by second period
        with pytest.raises(FiscalPeriodClosedError):
            assert_open_for_date([closed_q1, closed_q2], date(2026, 5, 15))

    def test_date_between_two_closed_periods_is_allowed(self) -> None:
        """Gap between two closed periods should not be blocked."""
        closed_jan = _closed_period(
            name="January 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        closed_mar = _closed_period(
            name="March 2026",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        feb_date = date(2026, 2, 15)
        assert_open_for_date([closed_jan, closed_mar], feb_date)  # gap — must not raise


# ===========================================================================
# Service — close_period
# ===========================================================================


class TestClosePeriodService:
    """close_period must close the period, register with session, and flush."""

    def test_close_period_sets_closed_status(self) -> None:
        period = _open_period()
        _run(close_period(_mock_session(), period))
        assert period.is_closed is True

    def test_close_period_returns_period(self) -> None:
        period = _open_period()
        result = _run(close_period(_mock_session(), period))
        assert result is period

    def test_close_period_adds_to_session(self) -> None:
        period = _open_period()
        session = _mock_session()
        _run(close_period(session, period))
        added_objects = [c.args[0] for c in session.add.call_args_list]
        assert period in added_objects

    def test_close_period_flushes_session(self) -> None:
        period = _open_period()
        session = _mock_session()
        _run(close_period(session, period))
        session.flush.assert_called_once()

    def test_close_already_closed_raises(self) -> None:
        period = _closed_period()
        with pytest.raises(FiscalPeriodAlreadyClosedError):
            _run(close_period(_mock_session(), period))

    def test_close_already_closed_does_not_flush(self) -> None:
        """Session must not be touched when the period is already closed."""
        period = _closed_period()
        session = _mock_session()
        with pytest.raises(FiscalPeriodAlreadyClosedError):
            _run(close_period(session, period))
        session.flush.assert_not_called()
        session.add.assert_not_called()


# ===========================================================================
# Module / package exports
# ===========================================================================


class TestModuleExports:
    """All public symbols must be importable from their documented locations."""

    def test_fiscal_period_importable_from_models(self) -> None:
        from cairnbooks.models.period import FiscalPeriod as FP  # noqa: F401
        assert FP is FiscalPeriod

    def test_period_status_importable_from_models(self) -> None:
        from cairnbooks.models.period import PeriodStatus as PS  # noqa: F401
        assert PS is PeriodStatus

    def test_close_period_importable_from_ledger(self) -> None:
        from cairnbooks.ledger.period import close_period as cp  # noqa: F401
        assert callable(cp)

    def test_assert_open_for_date_importable_from_ledger(self) -> None:
        from cairnbooks.ledger.period import assert_open_for_date as aof  # noqa: F401
        assert callable(aof)

    def test_fiscal_period_error_importable(self) -> None:
        from cairnbooks.models.period import FiscalPeriodError as FPE  # noqa: F401
        assert issubclass(FPE, Exception)
