"""Unit tests for Account model, AccountType, and COA seed.

These tests are pure-Python and do NOT require a running database,
async event loop, or any I/O.

Coverage
--------
- AccountType enum values and properties (normal_balance, is_balance_sheet,
  is_income_statement).
- Account ORM column / constraint metadata (no DB connection needed).
- activate / deactivate helpers.
- Domain exception hierarchy.
- default_coa_entries(): structure, ordering, idempotency, uniqueness.
"""

from __future__ import annotations

import uuid

import pytest

from cairnbooks.models.account import (
    Account,
    AccountError,
    AccountType,
    AccountTypeMismatchError,
    Base,
    InvalidAccountCodeError,
    InvalidAccountNameError,
    SelfReferenceError,
)
from cairnbooks.seed.coa import default_coa_entries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# ===========================================================================
# AccountType
# ===========================================================================


class TestAccountTypeValues:
    """Enum values must be stable across releases."""

    def test_asset_value(self) -> None:
        assert AccountType.ASSET.value == "asset"

    def test_liability_value(self) -> None:
        assert AccountType.LIABILITY.value == "liability"

    def test_equity_value(self) -> None:
        assert AccountType.EQUITY.value == "equity"

    def test_income_value(self) -> None:
        assert AccountType.INCOME.value == "income"

    def test_expense_value(self) -> None:
        assert AccountType.EXPENSE.value == "expense"

    def test_exactly_five_types(self) -> None:
        assert len(AccountType) == 5

    def test_str_enum_equals_value(self) -> None:
        """str Enum members compare equal to their string values."""
        assert AccountType.ASSET == "asset"
        assert AccountType.EXPENSE == "expense"


class TestAccountTypeNormalBalance:
    """Debit-normal: ASSET, EXPENSE.  Credit-normal: LIABILITY, EQUITY, INCOME."""

    @pytest.mark.parametrize("t", [AccountType.ASSET, AccountType.EXPENSE])
    def test_debit_normal(self, t: AccountType) -> None:
        assert t.normal_balance == "debit"

    @pytest.mark.parametrize(
        "t", [AccountType.LIABILITY, AccountType.EQUITY, AccountType.INCOME]
    )
    def test_credit_normal(self, t: AccountType) -> None:
        assert t.normal_balance == "credit"


class TestAccountTypeCategories:
    """Balance-sheet vs income-statement classification."""

    @pytest.mark.parametrize(
        "t", [AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY]
    )
    def test_balance_sheet(self, t: AccountType) -> None:
        assert t.is_balance_sheet is True
        assert t.is_income_statement is False

    @pytest.mark.parametrize("t", [AccountType.INCOME, AccountType.EXPENSE])
    def test_income_statement(self, t: AccountType) -> None:
        assert t.is_income_statement is True
        assert t.is_balance_sheet is False


# ===========================================================================
# Account ORM — metadata checks (no DB needed)
# ===========================================================================


class TestAccountORM:
    """ORM metadata must be fully wired without a database connection."""

    def test_tablename(self) -> None:
        assert Account.__tablename__ == "accounts"

    def test_required_columns_present(self) -> None:
        cols = {c.name for c in Account.__table__.columns}
        assert cols >= {
            "id",
            "company_id",
            "code",
            "name",
            "type",
            "parent_id",
            "active",
            "created_at",
            "updated_at",
        }

    def test_registered_in_base_metadata(self) -> None:
        assert "accounts" in Base.metadata.tables

    def test_company_id_fk(self) -> None:
        col = Account.__table__.c["company_id"]
        targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "companies.id" in targets

    def test_parent_id_self_fk(self) -> None:
        col = Account.__table__.c["parent_id"]
        targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "accounts.id" in targets

    def test_unique_constraint_company_code(self) -> None:
        """uq_accounts_company_code must be declared."""
        constraint_names = {
            c.name
            for c in Account.__table__.constraints
            if hasattr(c, "name") and c.name
        }
        assert "uq_accounts_company_code" in constraint_names

    def test_no_self_parent_check_constraint(self) -> None:
        """ck_accounts_no_self_parent must be declared."""
        constraint_names = {
            c.name
            for c in Account.__table__.constraints
            if hasattr(c, "name") and c.name
        }
        assert "ck_accounts_no_self_parent" in constraint_names


# ===========================================================================
# Account domain helpers
# ===========================================================================


class TestAccountNormalBalance:
    """Account.normal_balance delegates to AccountType."""

    def test_asset(self) -> None:
        a = Account(company_id=_COMPANY_ID, code="1000", name="Cash", type="asset")
        assert a.normal_balance == "debit"

    def test_liability(self) -> None:
        a = Account(company_id=_COMPANY_ID, code="2000", name="AP", type="liability")
        assert a.normal_balance == "credit"

    def test_equity(self) -> None:
        a = Account(
            company_id=_COMPANY_ID, code="3000", name="Retained Earnings", type="equity"
        )
        assert a.normal_balance == "credit"

    def test_income(self) -> None:
        a = Account(company_id=_COMPANY_ID, code="4000", name="Revenue", type="income")
        assert a.normal_balance == "credit"

    def test_expense(self) -> None:
        a = Account(company_id=_COMPANY_ID, code="5000", name="COGS", type="expense")
        assert a.normal_balance == "debit"


class TestAccountActivation:
    """activate() / deactivate() toggle the active flag."""

    def _account(self) -> Account:
        return Account(company_id=_COMPANY_ID, code="X", name="X", type="asset", active=True)

    def test_explicit_active_true(self) -> None:
        a = Account(company_id=_COMPANY_ID, code="X", name="X", type="asset", active=True)
        assert a.active is True

    def test_deactivate(self) -> None:
        a = self._account()
        a.deactivate()
        assert a.active is False

    def test_activate(self) -> None:
        a = Account(
            company_id=_COMPANY_ID, code="X", name="X", type="asset", active=False
        )
        a.activate()
        assert a.active is True

    def test_idempotent_deactivate(self) -> None:
        a = Account(
            company_id=_COMPANY_ID, code="X", name="X", type="asset", active=False
        )
        a.deactivate()
        assert a.active is False

    def test_idempotent_activate(self) -> None:
        a = self._account()
        a.activate()
        assert a.active is True


class TestParentCompatibility:
    """is_compatible_parent / assert_compatible_parent enforce type rules."""

    def _account(self, code: str, type_: str) -> Account:
        return Account(company_id=_COMPANY_ID, code=code, name=code, type=type_)

    @pytest.mark.parametrize("t", [at.value for at in AccountType])
    def test_same_type_compatible(self, t: str) -> None:
        parent = self._account("P", t)
        child = self._account("C", t)
        assert child.is_compatible_parent(parent) is True

    @pytest.mark.parametrize(
        ("child_t", "parent_t"),
        [
            ("asset", "liability"),
            ("asset", "equity"),
            ("income", "expense"),
            ("expense", "income"),
            ("liability", "asset"),
        ],
    )
    def test_different_type_incompatible(self, child_t: str, parent_t: str) -> None:
        parent = self._account("P", parent_t)
        child = self._account("C", child_t)
        assert child.is_compatible_parent(parent) is False

    def test_assert_raises_on_mismatch(self) -> None:
        parent = self._account("P", "asset")
        child = self._account("C", "liability")
        with pytest.raises(AccountTypeMismatchError):
            child.assert_compatible_parent(parent)

    def test_assert_no_raise_on_match(self) -> None:
        parent = self._account("P", "income")
        child = self._account("C", "income")
        child.assert_compatible_parent(parent)  # must not raise

    def test_mismatch_is_account_error(self) -> None:
        parent = self._account("P", "asset")
        child = self._account("C", "expense")
        with pytest.raises(AccountError):
            child.assert_compatible_parent(parent)


# ===========================================================================
# Exception hierarchy
# ===========================================================================


class TestExceptionHierarchy:
    """All domain exceptions must derive from AccountError."""

    def test_invalid_code_is_account_error(self) -> None:
        assert issubclass(InvalidAccountCodeError, AccountError)

    def test_invalid_name_is_account_error(self) -> None:
        assert issubclass(InvalidAccountNameError, AccountError)

    def test_type_mismatch_is_account_error(self) -> None:
        assert issubclass(AccountTypeMismatchError, AccountError)

    def test_self_reference_is_account_error(self) -> None:
        assert issubclass(SelfReferenceError, AccountError)


# ===========================================================================
# Default COA seed
# ===========================================================================


class TestDefaultCoaEntries:
    """default_coa_entries() must return well-formed, ordered COA data."""

    def _entries(self) -> list[dict]:
        return default_coa_entries(_COMPANY_ID)

    def test_returns_list(self) -> None:
        assert isinstance(self._entries(), list)

    def test_non_empty(self) -> None:
        assert len(self._entries()) > 0

    def test_covers_all_five_types(self) -> None:
        types = {e["type"] for e in self._entries()}
        assert types == {"asset", "liability", "equity", "income", "expense"}

    def test_required_keys(self) -> None:
        for entry in self._entries():
            assert {"id", "company_id", "code", "name", "type", "parent_id", "active"} <= set(
                entry.keys()
            )

    def test_codes_unique(self) -> None:
        codes = [e["code"] for e in self._entries()]
        assert len(codes) == len(set(codes))

    def test_ids_unique(self) -> None:
        ids = [e["id"] for e in self._entries()]
        assert len(ids) == len(set(ids))

    def test_ids_are_valid_uuids(self) -> None:
        for entry in self._entries():
            uuid.UUID(entry["id"])  # raises ValueError if invalid

    def test_company_id_matches_arg(self) -> None:
        for entry in self._entries():
            assert entry["company_id"] == str(_COMPANY_ID)

    def test_all_active_by_default(self) -> None:
        assert all(e["active"] is True for e in self._entries())

    def test_type_values_valid(self) -> None:
        valid = {t.value for t in AccountType}
        for entry in self._entries():
            assert entry["type"] in valid

    def test_parent_ids_reference_existing_ids(self) -> None:
        entries = self._entries()
        all_ids = {e["id"] for e in entries}
        for entry in entries:
            if entry["parent_id"] is not None:
                assert entry["parent_id"] in all_ids

    def test_parents_precede_children(self) -> None:
        """Every parent must appear before its first child in the list."""
        entries = self._entries()
        seen: set[str] = set()
        for entry in entries:
            if entry["parent_id"] is not None:
                assert entry["parent_id"] in seen, (
                    f"Account {entry['code']!r}: parent {entry['parent_id']!r} "
                    "has not been seen yet — ordering invariant violated"
                )
            seen.add(entry["id"])

    def test_idempotent(self) -> None:
        """Two calls with the same company_id return identical data."""
        assert default_coa_entries(_COMPANY_ID) == default_coa_entries(_COMPANY_ID)

    def test_different_company_ids_give_same_structure(self) -> None:
        """Structure (codes, names, types) is identical for any company_id."""
        cid2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
        e1 = default_coa_entries(_COMPANY_ID)
        e2 = default_coa_entries(cid2)
        assert len(e1) == len(e2)
        for a, b in zip(e1, e2):
            assert a["code"] == b["code"]
            assert a["type"] == b["type"]
            assert a["name"] == b["name"]

    def test_header_accounts_present(self) -> None:
        codes = {e["code"] for e in self._entries()}
        for code in ("1000", "2000", "3000", "4000", "5000"):
            assert code in codes

    def test_header_accounts_have_no_parent(self) -> None:
        entries = self._entries()
        headers = {
            e["code"]: e
            for e in entries
            if e["code"] in ("1000", "2000", "3000", "4000", "5000")
        }
        for code, entry in headers.items():
            assert entry["parent_id"] is None, (
                f"Header account {code!r} should have no parent"
            )
