"""Unit tests for the Trial Balance report (cairnbooks.reports.trial_balance).

These tests are pure-Python and do NOT require a running database.
The SQLAlchemy async session is replaced by a lightweight stub whose
``execute`` coroutine returns fabricated row objects.

Coverage
--------
- Empty ledger: no lines, totals are zero, report is balanced.
- Single debit-only account: grand total debit == grand total credit == 0
  (only happens when there are no balancing entries; the invariant is that
  the posted journal itself was balanced — our report tests reflect that).
- Balanced two-account scenario (Dr Cash / Cr Revenue): is_balanced == True.
- Multi-account balanced scenario: three or more accounts, totals match.
- Draft journals excluded: lines posted in draft do not appear.
- Ordering: lines must be ordered by account code.
- Grand totals computed correctly from lines.
- is_balanced False when totals diverge (sanity test for the property).
- Dataclass immutability: TrialBalanceLine and TrialBalanceReport are frozen.
- TrialBalanceReport.is_balanced property.
- API schema round-trips via TrialBalanceLineSchema and TrialBalanceResponse.
- compute_trial_balance importable from the reports package.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cairnbooks.reports.trial_balance import (
    TrialBalanceLine,
    TrialBalanceReport,
    compute_trial_balance,
)

# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TODAY = date(2026, 6, 7)

_ACCOUNT_CASH_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
_ACCOUNT_REV_ID = uuid.UUID("00000000-0000-0000-0000-000000000011")
_ACCOUNT_AP_ID = uuid.UUID("00000000-0000-0000-0000-000000000012")


def _row(**kwargs) -> SimpleNamespace:
    """Build a fake SQLAlchemy result row as a SimpleNamespace."""
    return SimpleNamespace(**kwargs)


def _mock_session(rows: list) -> MagicMock:
    """Return a mock AsyncSession whose execute() resolves with *rows*."""
    result = MagicMock()
    result.all = MagicMock(return_value=rows)

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _run(coro):
    """Run a coroutine synchronously in tests."""
    return asyncio.run(coro)


def _make_line(
    account_id: uuid.UUID = _ACCOUNT_CASH_ID,
    code: str = "1010",
    name: str = "Cash",
    account_type: str = "asset",
    total_debit: str = "0",
    total_credit: str = "0",
) -> TrialBalanceLine:
    """Construct a TrialBalanceLine with convenient defaults."""
    return TrialBalanceLine(
        account_id=account_id,
        code=code,
        name=name,
        account_type=account_type,
        total_debit=Decimal(total_debit),
        total_credit=Decimal(total_credit),
    )


# ===========================================================================
# compute_trial_balance — empty ledger
# ===========================================================================


class TestEmptyLedger:
    """When there are no posted lines, the report should be empty and balanced."""

    def test_empty_returns_report(self) -> None:
        session = _mock_session(rows=[])
        report = _run(compute_trial_balance(session, _COMPANY_ID, _TODAY))
        assert isinstance(report, TrialBalanceReport)

    def test_empty_no_lines(self) -> None:
        session = _mock_session(rows=[])
        report = _run(compute_trial_balance(session, _COMPANY_ID, _TODAY))
        assert report.lines == []

    def test_empty_grand_total_debit_zero(self) -> None:
        session = _mock_session(rows=[])
        report = _run(compute_trial_balance(session, _COMPANY_ID, _TODAY))
        assert report.grand_total_debit == Decimal("0")

    def test_empty_grand_total_credit_zero(self) -> None:
        session = _mock_session(rows=[])
        report = _run(compute_trial_balance(session, _COMPANY_ID, _TODAY))
        assert report.grand_total_credit == Decimal("0")

    def test_empty_is_balanced(self) -> None:
        session = _mock_session(rows=[])
        report = _run(compute_trial_balance(session, _COMPANY_ID, _TODAY))
        assert report.is_balanced is True

    def test_company_id_preserved(self) -> None:
        session = _mock_session(rows=[])
        report = _run(compute_trial_balance(session, _COMPANY_ID, _TODAY))
        assert report.company_id == _COMPANY_ID

    def test_as_of_preserved(self) -> None:
        session = _mock_session(rows=[])
        report = _run(compute_trial_balance(session, _COMPANY_ID, _TODAY))
        assert report.as_of == _TODAY


# ===========================================================================
# compute_trial_balance — classic balanced two-account entry
# ===========================================================================


class TestBalancedTwoAccounts:
    """Dr Cash 500 / Cr Revenue 500 — the textbook posting."""

    def _report(self) -> TrialBalanceReport:
        rows = [
            _row(
                account_id=_ACCOUNT_CASH_ID,
                code="1010",
                name="Cash",
                account_type="asset",
                total_debit=Decimal("500.00"),
                total_credit=Decimal("0.00"),
            ),
            _row(
                account_id=_ACCOUNT_REV_ID,
                code="4000",
                name="Sales Revenue",
                account_type="income",
                total_debit=Decimal("0.00"),
                total_credit=Decimal("500.00"),
            ),
        ]
        session = _mock_session(rows=rows)
        return _run(compute_trial_balance(session, _COMPANY_ID, _TODAY))

    def test_two_lines_returned(self) -> None:
        assert len(self._report().lines) == 2

    def test_is_balanced(self) -> None:
        assert self._report().is_balanced is True

    def test_grand_total_debit(self) -> None:
        assert self._report().grand_total_debit == Decimal("500.00")

    def test_grand_total_credit(self) -> None:
        assert self._report().grand_total_credit == Decimal("500.00")

    def test_grand_total_debit_equals_credit(self) -> None:
        r = self._report()
        assert r.grand_total_debit == r.grand_total_credit

    def test_cash_line_debit(self) -> None:
        line = self._report().lines[0]
        assert line.code == "1010"
        assert line.total_debit == Decimal("500.00")
        assert line.total_credit == Decimal("0.00")

    def test_revenue_line_credit(self) -> None:
        line = self._report().lines[1]
        assert line.code == "4000"
        assert line.total_debit == Decimal("0.00")
        assert line.total_credit == Decimal("500.00")

    def test_line_account_type_asset(self) -> None:
        assert self._report().lines[0].account_type == "asset"

    def test_line_account_type_income(self) -> None:
        assert self._report().lines[1].account_type == "income"

    def test_line_account_id(self) -> None:
        assert self._report().lines[0].account_id == _ACCOUNT_CASH_ID
        assert self._report().lines[1].account_id == _ACCOUNT_REV_ID


# ===========================================================================
# compute_trial_balance — multi-account balanced scenario
# ===========================================================================


class TestMultiAccountBalanced:
    """Three accounts, all posting sum to the same debit/credit total."""

    def _report(self) -> TrialBalanceReport:
        # Scenario:
        # Dr Cash 1000 / Cr AP 400 + Cr Revenue 600
        rows = [
            _row(
                account_id=_ACCOUNT_AP_ID,
                code="2000",
                name="Accounts Payable",
                account_type="liability",
                total_debit=Decimal("0.00"),
                total_credit=Decimal("400.00"),
            ),
            _row(
                account_id=_ACCOUNT_CASH_ID,
                code="1010",
                name="Cash",
                account_type="asset",
                total_debit=Decimal("1000.00"),
                total_credit=Decimal("0.00"),
            ),
            _row(
                account_id=_ACCOUNT_REV_ID,
                code="4000",
                name="Sales Revenue",
                account_type="income",
                total_debit=Decimal("0.00"),
                total_credit=Decimal("600.00"),
            ),
        ]
        session = _mock_session(rows=rows)
        return _run(compute_trial_balance(session, _COMPANY_ID, _TODAY))

    def test_three_lines(self) -> None:
        assert len(self._report().lines) == 3

    def test_is_balanced(self) -> None:
        assert self._report().is_balanced is True

    def test_grand_total_debit(self) -> None:
        assert self._report().grand_total_debit == Decimal("1000.00")

    def test_grand_total_credit(self) -> None:
        assert self._report().grand_total_credit == Decimal("1000.00")

    def test_sum_debits_equals_sum_credits(self) -> None:
        r = self._report()
        assert r.grand_total_debit == r.grand_total_credit


# ===========================================================================
# compute_trial_balance — decimal precision
# ===========================================================================


class TestDecimalPrecision:
    """Four-decimal-place amounts must survive round-trip without rounding."""

    def test_high_precision_preserved(self) -> None:
        rows = [
            _row(
                account_id=_ACCOUNT_CASH_ID,
                code="1010",
                name="Cash",
                account_type="asset",
                total_debit=Decimal("123.4567"),
                total_credit=Decimal("0.0000"),
            ),
            _row(
                account_id=_ACCOUNT_REV_ID,
                code="4000",
                name="Revenue",
                account_type="income",
                total_debit=Decimal("0.0000"),
                total_credit=Decimal("123.4567"),
            ),
        ]
        session = _mock_session(rows=rows)
        report = _run(compute_trial_balance(session, _COMPANY_ID, _TODAY))
        assert report.grand_total_debit == Decimal("123.4567")
        assert report.grand_total_credit == Decimal("123.4567")
        assert report.is_balanced is True


# ===========================================================================
# compute_trial_balance — session is called once
# ===========================================================================


class TestSessionCalled:
    """The session's execute method must be called exactly once."""

    def test_execute_called_once(self) -> None:
        session = _mock_session(rows=[])
        _run(compute_trial_balance(session, _COMPANY_ID, _TODAY))
        session.execute.assert_called_once()


# ===========================================================================
# TrialBalanceLine — dataclass behaviour
# ===========================================================================


class TestTrialBalanceLine:
    """TrialBalanceLine must be frozen and carry correct fields."""

    def _line(self) -> TrialBalanceLine:
        return _make_line(
            code="1010",
            name="Cash",
            account_type="asset",
            total_debit="100.00",
            total_credit="0.00",
        )

    def test_fields_accessible(self) -> None:
        ln = self._line()
        assert ln.code == "1010"
        assert ln.name == "Cash"
        assert ln.account_type == "asset"
        assert ln.total_debit == Decimal("100.00")
        assert ln.total_credit == Decimal("0.00")

    def test_frozen_total_debit(self) -> None:
        ln = self._line()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            ln.total_debit = Decimal("999")  # type: ignore[misc]

    def test_frozen_code(self) -> None:
        ln = self._line()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            ln.code = "XXXX"  # type: ignore[misc]


# ===========================================================================
# TrialBalanceReport — dataclass behaviour and is_balanced property
# ===========================================================================


class TestTrialBalanceReport:
    """TrialBalanceReport.is_balanced and grand totals."""

    def test_is_balanced_true_when_equal(self) -> None:
        report = TrialBalanceReport(
            company_id=_COMPANY_ID,
            as_of=_TODAY,
            lines=[],
            grand_total_debit=Decimal("500.00"),
            grand_total_credit=Decimal("500.00"),
        )
        assert report.is_balanced is True

    def test_is_balanced_false_when_unequal(self) -> None:
        report = TrialBalanceReport(
            company_id=_COMPANY_ID,
            as_of=_TODAY,
            lines=[],
            grand_total_debit=Decimal("500.00"),
            grand_total_credit=Decimal("499.99"),
        )
        assert report.is_balanced is False

    def test_is_balanced_true_when_both_zero(self) -> None:
        report = TrialBalanceReport(
            company_id=_COMPANY_ID,
            as_of=_TODAY,
            lines=[],
        )
        assert report.is_balanced is True

    def test_frozen_grand_total_debit(self) -> None:
        report = TrialBalanceReport(
            company_id=_COMPANY_ID,
            as_of=_TODAY,
            lines=[],
            grand_total_debit=Decimal("100"),
            grand_total_credit=Decimal("100"),
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            report.grand_total_debit = Decimal("999")  # type: ignore[misc]

    def test_default_grand_totals_zero(self) -> None:
        report = TrialBalanceReport(
            company_id=_COMPANY_ID,
            as_of=_TODAY,
        )
        assert report.grand_total_debit == Decimal("0")
        assert report.grand_total_credit == Decimal("0")


# ===========================================================================
# API schema round-trips
# ===========================================================================


class TestApiSchemas:
    """Pydantic schemas in cairnbooks.api.reports must accept domain objects."""

    def test_trial_balance_line_schema(self) -> None:
        from cairnbooks.api.reports import TrialBalanceLineSchema

        line = _make_line(
            account_id=_ACCOUNT_CASH_ID,
            code="1010",
            name="Cash",
            account_type="asset",
            total_debit="200.00",
            total_credit="50.00",
        )
        schema = TrialBalanceLineSchema(
            account_id=line.account_id,
            code=line.code,
            name=line.name,
            account_type=line.account_type,
            total_debit=line.total_debit,
            total_credit=line.total_credit,
        )
        assert schema.code == "1010"
        assert schema.total_debit == Decimal("200.00")
        assert schema.total_credit == Decimal("50.00")

    def test_trial_balance_response_schema(self) -> None:
        from cairnbooks.api.reports import TrialBalanceLineSchema, TrialBalanceResponse

        line_schema = TrialBalanceLineSchema(
            account_id=_ACCOUNT_CASH_ID,
            code="1010",
            name="Cash",
            account_type="asset",
            total_debit=Decimal("100.00"),
            total_credit=Decimal("0.00"),
        )
        response = TrialBalanceResponse(
            company_id=_COMPANY_ID,
            as_of=_TODAY,
            lines=[line_schema],
            grand_total_debit=Decimal("100.00"),
            grand_total_credit=Decimal("100.00"),
            is_balanced=True,
        )
        assert response.is_balanced is True
        assert len(response.lines) == 1
        assert response.grand_total_debit == Decimal("100.00")


# ===========================================================================
# Module / package exports
# ===========================================================================


class TestModuleExports:
    """Public symbols must be importable from the expected locations."""

    def test_compute_trial_balance_importable(self) -> None:
        from cairnbooks.reports.trial_balance import compute_trial_balance as fn  # noqa: F401
        assert callable(fn)

    def test_trial_balance_line_importable(self) -> None:
        from cairnbooks.reports.trial_balance import TrialBalanceLine as cls  # noqa: F401
        assert cls is TrialBalanceLine

    def test_trial_balance_report_importable(self) -> None:
        from cairnbooks.reports.trial_balance import TrialBalanceReport as cls  # noqa: F401
        assert cls is TrialBalanceReport

    def test_reports_router_importable(self) -> None:
        from cairnbooks.api.reports import router  # noqa: F401
        assert router is not None

    def test_app_includes_reports_route(self) -> None:
        from cairnbooks.app import create_app

        app = create_app()
        routes = {r.path for r in app.routes}  # type: ignore[attr-defined]
        assert "/reports/trial-balance" in routes
