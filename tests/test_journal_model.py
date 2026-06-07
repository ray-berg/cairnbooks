"""Unit tests for Journal and JournalLine models.

These tests are pure-Python and do NOT require a running database,
async event loop, or any I/O.

Coverage
--------
- JournalStatus enum values and string comparison.
- Journal ORM column / constraint metadata (no DB connection).
- Journal domain methods: is_posted, assert_not_posted, post().
- JournalLine ORM column / constraint metadata (no DB connection).
- Immutability guard: modifying guarded fields on a posted line raises
  JournalPostedError.
- Exception hierarchy (JournalPostedError, JournalImbalancedError ≤ JournalError).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

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
_ACCOUNT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_TODAY = date(2026, 6, 7)


def _draft_journal(**kwargs) -> Journal:
    """Return a minimal draft journal."""
    defaults = dict(
        company_id=_COMPANY_ID,
        date=_TODAY,
        status=JournalStatus.DRAFT,
    )
    defaults.update(kwargs)
    return Journal(**defaults)


def _posted_journal(**kwargs) -> Journal:
    """Return a journal that has been posted."""
    j = _draft_journal(**kwargs)
    j.post()
    return j


def _line(journal: Journal | None = None, **kwargs) -> JournalLine:
    """Return a minimal JournalLine, optionally wired to *journal*."""
    defaults = dict(
        account_id=_ACCOUNT_ID,
        debit=Decimal("100.00"),
        credit=Decimal("0.00"),
        line_number=1,
    )
    defaults.update(kwargs)
    line = JournalLine(**defaults)
    if journal is not None:
        # Wire up the in-memory relationship so the guard can inspect it.
        line.journal = journal
    return line


# ===========================================================================
# JournalStatus
# ===========================================================================


class TestJournalStatusValues:
    """Enum values must be stable string literals."""

    def test_draft_value(self) -> None:
        assert JournalStatus.DRAFT.value == "draft"

    def test_posted_value(self) -> None:
        assert JournalStatus.POSTED.value == "posted"

    def test_exactly_two_statuses(self) -> None:
        assert len(JournalStatus) == 2

    def test_str_enum_equals_value(self) -> None:
        assert JournalStatus.DRAFT == "draft"
        assert JournalStatus.POSTED == "posted"


# ===========================================================================
# Journal ORM metadata (no DB)
# ===========================================================================


class TestJournalORM:
    """ORM metadata must be fully wired without a database connection."""

    def test_tablename(self) -> None:
        assert Journal.__tablename__ == "journals"

    def test_required_columns_present(self) -> None:
        cols = {c.name for c in Journal.__table__.columns}
        assert cols >= {
            "id",
            "company_id",
            "date",
            "reference",
            "description",
            "status",
            "created_at",
            "updated_at",
        }

    def test_company_id_fk_to_companies(self) -> None:
        col = Journal.__table__.c["company_id"]
        targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "companies.id" in targets

    def test_status_check_constraint_declared(self) -> None:
        names = {
            c.name
            for c in Journal.__table__.constraints
            if hasattr(c, "name") and c.name
        }
        assert "ck_journals_status" in names

    def test_default_status_is_draft(self) -> None:
        j = _draft_journal()
        assert j.status == JournalStatus.DRAFT

    def test_registered_in_metadata(self) -> None:
        from cairnbooks.db import Base

        assert "journals" in Base.metadata.tables


# ===========================================================================
# JournalLine ORM metadata (no DB)
# ===========================================================================


class TestJournalLineORM:
    """ORM metadata for journal_lines must be fully wired."""

    def test_tablename(self) -> None:
        assert JournalLine.__tablename__ == "journal_lines"

    def test_required_columns_present(self) -> None:
        cols = {c.name for c in JournalLine.__table__.columns}
        assert cols >= {
            "id",
            "journal_id",
            "account_id",
            "debit",
            "credit",
            "description",
            "line_number",
            "created_at",
        }

    def test_journal_id_fk_to_journals(self) -> None:
        col = JournalLine.__table__.c["journal_id"]
        targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "journals.id" in targets

    def test_account_id_fk_to_accounts(self) -> None:
        col = JournalLine.__table__.c["account_id"]
        targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "accounts.id" in targets

    def test_debit_nonneg_check_declared(self) -> None:
        names = {
            c.name
            for c in JournalLine.__table__.constraints
            if hasattr(c, "name") and c.name
        }
        assert "ck_journal_lines_debit_nonneg" in names

    def test_credit_nonneg_check_declared(self) -> None:
        names = {
            c.name
            for c in JournalLine.__table__.constraints
            if hasattr(c, "name") and c.name
        }
        assert "ck_journal_lines_credit_nonneg" in names

    def test_debit_column_is_numeric(self) -> None:
        from sqlalchemy import Numeric

        col = JournalLine.__table__.c["debit"]
        assert isinstance(col.type, Numeric)

    def test_credit_column_is_numeric(self) -> None:
        from sqlalchemy import Numeric

        col = JournalLine.__table__.c["credit"]
        assert isinstance(col.type, Numeric)

    def test_registered_in_metadata(self) -> None:
        from cairnbooks.db import Base

        assert "journal_lines" in Base.metadata.tables

    def test_debit_server_default_is_zero(self) -> None:
        """server_default ensures the DB inserts 0 when debit is omitted."""
        col = JournalLine.__table__.c["debit"]
        assert col.server_default is not None
        assert "0" in str(col.server_default.arg)

    def test_credit_server_default_is_zero(self) -> None:
        """server_default ensures the DB inserts 0 when credit is omitted."""
        col = JournalLine.__table__.c["credit"]
        assert col.server_default is not None
        assert "0" in str(col.server_default.arg)


# ===========================================================================
# Journal domain methods
# ===========================================================================


class TestJournalIsPosted:
    """is_posted reflects the status field."""

    def test_draft_not_posted(self) -> None:
        j = _draft_journal()
        assert j.is_posted is False

    def test_posted_is_posted(self) -> None:
        j = _posted_journal()
        assert j.is_posted is True


class TestJournalAssertNotPosted:
    """assert_not_posted raises only for posted journals."""

    def test_draft_does_not_raise(self) -> None:
        j = _draft_journal()
        j.assert_not_posted()  # must not raise

    def test_posted_raises(self) -> None:
        j = _posted_journal()
        with pytest.raises(JournalPostedError):
            j.assert_not_posted()

    def test_posted_raises_journal_error(self) -> None:
        j = _posted_journal()
        with pytest.raises(JournalError):
            j.assert_not_posted()


class TestJournalPost:
    """Journal.post() transitions draft → posted."""

    def test_post_sets_posted_status(self) -> None:
        j = _draft_journal()
        j.post()
        assert j.status == JournalStatus.POSTED

    def test_post_makes_is_posted_true(self) -> None:
        j = _draft_journal()
        j.post()
        assert j.is_posted is True

    def test_double_post_raises(self) -> None:
        j = _draft_journal()
        j.post()
        with pytest.raises(JournalPostedError):
            j.post()

    def test_double_post_raises_journal_error(self) -> None:
        j = _draft_journal()
        j.post()
        with pytest.raises(JournalError):
            j.post()


# ===========================================================================
# JournalLine immutability guard
# ===========================================================================


class TestJournalLineGuard:
    """Guarded fields on lines wired to a posted journal must be immutable."""

    def test_draft_journal_allows_debit_change(self) -> None:
        j = _draft_journal()
        line = _line(journal=j, debit=Decimal("100.00"))
        line.debit = Decimal("200.00")  # must not raise
        assert line.debit == Decimal("200.00")

    def test_draft_journal_allows_credit_change(self) -> None:
        j = _draft_journal()
        line = _line(journal=j, credit=Decimal("50.00"))
        line.credit = Decimal("75.00")  # must not raise

    def test_no_journal_allows_debit_change(self) -> None:
        """Lines without a journal wired in are always mutable."""
        line = _line()
        line.debit = Decimal("999.00")  # must not raise

    def test_posted_journal_blocks_debit(self) -> None:
        j = _posted_journal()
        line = _line(journal=j)
        with pytest.raises(JournalPostedError):
            line.debit = Decimal("999.00")

    def test_posted_journal_blocks_credit(self) -> None:
        j = _posted_journal()
        line = _line(journal=j)
        with pytest.raises(JournalPostedError):
            line.credit = Decimal("999.00")

    def test_posted_journal_blocks_account_id(self) -> None:
        j = _posted_journal()
        line = _line(journal=j)
        with pytest.raises(JournalPostedError):
            line.account_id = uuid.UUID("00000000-0000-0000-0000-000000000099")

    def test_posted_journal_blocks_description(self) -> None:
        j = _posted_journal()
        line = _line(journal=j)
        with pytest.raises(JournalPostedError):
            line.description = "changed"

    def test_posted_journal_blocks_line_number(self) -> None:
        j = _posted_journal()
        line = _line(journal=j)
        with pytest.raises(JournalPostedError):
            line.line_number = 2

    def test_guard_raises_journal_error(self) -> None:
        """JournalPostedError must be a subclass of JournalError."""
        j = _posted_journal()
        line = _line(journal=j)
        with pytest.raises(JournalError):
            line.debit = Decimal("1.00")

    def test_construction_with_posted_journal_after_wiring(self) -> None:
        """Initial construction is allowed; guard fires only after journal is wired."""
        j = _posted_journal()
        # Create line first (no journal in __dict__ yet)
        line = JournalLine(account_id=_ACCOUNT_ID, debit=Decimal("50.00"))
        # Wire journal — now guard is active
        line.journal = j
        # Any subsequent mutation must be blocked
        with pytest.raises(JournalPostedError):
            line.debit = Decimal("75.00")


# ===========================================================================
# Exception hierarchy
# ===========================================================================


class TestExceptionHierarchy:
    """All Journal domain exceptions must derive from JournalError."""

    def test_posted_error_is_journal_error(self) -> None:
        assert issubclass(JournalPostedError, JournalError)

    def test_imbalanced_error_is_journal_error(self) -> None:
        assert issubclass(JournalImbalancedError, JournalError)

    def test_journal_error_is_exception(self) -> None:
        assert issubclass(JournalError, Exception)


# ===========================================================================
# Journal repr
# ===========================================================================


class TestJournalRepr:
    """__repr__ must be informative and not crash."""

    def test_repr_contains_status(self) -> None:
        j = _draft_journal()
        assert "draft" in repr(j)

    def test_posted_repr_contains_posted(self) -> None:
        j = _posted_journal()
        assert "posted" in repr(j)

    def test_line_repr_contains_debit(self) -> None:
        line = _line(debit=Decimal("42.00"))
        assert "42" in repr(line)
