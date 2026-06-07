"""Tests for BankAccount model and CRUD endpoints.

Coverage
--------
Model tests (no DB connection required):
- Table name and Base.metadata registration.
- Column metadata: types, nullability, defaults, lengths.
- Foreign key declarations (company_id → companies, gl_account_id → accounts).
- Unique constraint and index declarations.
- Domain helpers: activate / deactivate.
- __repr__ output.

Pydantic schema tests:
- BankAccountCreate field defaults and required fields.
- BankAccountUpdate all-optional contract.
- BankAccountRead model_config from_attributes.

API endpoint tests (TestClient + mocked AsyncSession):
- POST /bank-accounts → 201 with created object.
- GET  /bank-accounts → 200 with list.
- GET  /bank-accounts/{id} → 200 / 404.
- PATCH /bank-accounts/{id} → 200 with updated fields / 404.
- DELETE /bank-accounts/{id} → 204 / 404.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from starlette.testclient import TestClient

from cairnbooks.db import Base
from cairnbooks.models.bank_account import BankAccount

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_GL_ACCOUNT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_BANK_ACCOUNT_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
_NOW = datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC)


def _make_bank_account(**overrides) -> BankAccount:
    """Build a BankAccount ORM object with sensible defaults."""
    defaults = dict(
        id=_BANK_ACCOUNT_ID,
        company_id=_COMPANY_ID,
        gl_account_id=_GL_ACCOUNT_ID,
        name="Main Checking",
        account_number="xxxx-1234",
        routing_number="021000021",
        bank_name="First National Bank",
        currency="USD",
        active=True,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return BankAccount(**defaults)


def _apply_column_defaults(obj) -> None:
    """Apply Python-side SQLAlchemy column defaults to an un-flushed ORM object.

    In a real session, SQLAlchemy calls these during ``flush()`` before
    generating the INSERT.  Our mock flush is a no-op, so we replicate
    the logic here so that ``refresh()`` leaves the object in a fully
    populated state.

    SQLAlchemy wraps every callable default in a one-argument shim that
    receives the ``DefaultExecutionContext``; passing ``None`` as that
    context is sufficient for zero-argument generators such as
    ``uuid.uuid4`` and ``datetime.now``.
    """
    table = obj.__class__.__table__
    for col in table.c:
        if col.default is None:
            continue
        current = getattr(obj, col.name, None)
        if current is not None:
            continue
        arg = col.default.arg
        if callable(arg):
            try:
                val = arg(None)  # SQLAlchemy shim: fn(ctx) where ctx may be None
            except TypeError:
                val = arg()  # fallback for un-wrapped callables
        else:
            val = arg
        setattr(obj, col.name, val)


def _make_mock_session(
    bank_account: BankAccount | None = None,
    bank_accounts: list[BankAccount] | None = None,
) -> MagicMock:
    """Return a MagicMock that quacks like an AsyncSession."""
    session = MagicMock()

    # Synchronous methods
    session.add = MagicMock()
    session.delete = AsyncMock()

    # Asynchronous helpers
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    # refresh() simulates what a real DB round-trip would populate:
    # any column defaults that flush() would have evaluated.
    async def _refresh(obj):
        _apply_column_defaults(obj)

    session.refresh = _refresh

    # execute() returns a mock result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = bank_account
    rows = bank_accounts if bank_accounts is not None else (
        [bank_account] if bank_account else []
    )
    mock_result.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=mock_result)

    return session


def _make_test_client(mock_session: MagicMock) -> TestClient:
    """Build a TestClient with get_db overridden to use *mock_session*."""
    from cairnbooks.app import create_app
    from cairnbooks.db import get_db

    async def override_get_db() -> AsyncGenerator:  # type: ignore[type-arg]
        yield mock_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# ===========================================================================
# Model tests — no DB required
# ===========================================================================


class TestBankAccountTableMetadata:
    def test_tablename(self) -> None:
        assert BankAccount.__tablename__ == "bank_accounts"

    def test_registered_on_base_metadata(self) -> None:
        assert "bank_accounts" in Base.metadata.tables


class TestBankAccountColumns:
    """Verify column types, nullability, and defaults via ORM metadata."""

    def test_id_has_callable_default(self) -> None:
        from sqlalchemy.sql.schema import CallableColumnDefault

        col_default = BankAccount.__table__.c.id.default
        assert isinstance(col_default, CallableColumnDefault)

    def test_id_is_primary_key(self) -> None:
        assert BankAccount.__table__.c.id.primary_key

    def test_company_id_not_nullable(self) -> None:
        assert not BankAccount.__table__.c.company_id.nullable

    def test_gl_account_id_not_nullable(self) -> None:
        assert not BankAccount.__table__.c.gl_account_id.nullable

    def test_name_max_length(self) -> None:
        assert BankAccount.__table__.c.name.type.length == 255

    def test_account_number_nullable(self) -> None:
        assert BankAccount.__table__.c.account_number.nullable

    def test_account_number_max_length(self) -> None:
        assert BankAccount.__table__.c.account_number.type.length == 50

    def test_routing_number_nullable(self) -> None:
        assert BankAccount.__table__.c.routing_number.nullable

    def test_routing_number_max_length(self) -> None:
        assert BankAccount.__table__.c.routing_number.type.length == 20

    def test_bank_name_nullable(self) -> None:
        assert BankAccount.__table__.c.bank_name.nullable

    def test_currency_max_length(self) -> None:
        assert BankAccount.__table__.c.currency.type.length == 3

    def test_currency_python_default_is_usd(self) -> None:
        col_default = BankAccount.__table__.c.currency.default
        assert col_default is not None
        assert col_default.arg == "USD"

    def test_active_python_default_is_true(self) -> None:
        col_default = BankAccount.__table__.c.active.default
        assert col_default is not None
        assert col_default.arg is True

    def test_active_not_nullable(self) -> None:
        assert not BankAccount.__table__.c.active.nullable

    def test_created_at_not_nullable(self) -> None:
        assert not BankAccount.__table__.c.created_at.nullable

    def test_updated_at_not_nullable(self) -> None:
        assert not BankAccount.__table__.c.updated_at.nullable


class TestBankAccountForeignKeys:
    def test_company_id_fk_targets_companies(self) -> None:
        fks = BankAccount.__table__.c.company_id.foreign_keys
        assert len(fks) == 1
        (fk,) = fks
        assert fk.column.table.name == "companies"
        assert fk.column.name == "id"

    def test_company_id_fk_on_delete_cascade(self) -> None:
        fks = BankAccount.__table__.c.company_id.foreign_keys
        (fk,) = fks
        assert fk.ondelete.upper() == "CASCADE"

    def test_gl_account_id_fk_targets_accounts(self) -> None:
        fks = BankAccount.__table__.c.gl_account_id.foreign_keys
        assert len(fks) == 1
        (fk,) = fks
        assert fk.column.table.name == "accounts"
        assert fk.column.name == "id"

    def test_gl_account_id_fk_on_delete_restrict(self) -> None:
        fks = BankAccount.__table__.c.gl_account_id.foreign_keys
        (fk,) = fks
        assert fk.ondelete.upper() == "RESTRICT"


class TestBankAccountConstraintsAndIndexes:
    def test_unique_constraint_company_name_declared(self) -> None:
        constraint_names = {c.name for c in BankAccount.__table__.constraints}
        assert "uq_bank_accounts_company_name" in constraint_names

    def test_composite_index_company_active_declared(self) -> None:
        index_names = {i.name for i in BankAccount.__table__.indexes}
        assert "ix_bank_accounts_company_active" in index_names


class TestBankAccountInstantiation:
    def test_create_with_required_fields(self) -> None:
        ba = BankAccount(
            company_id=_COMPANY_ID,
            gl_account_id=_GL_ACCOUNT_ID,
            name="Payroll Checking",
        )
        assert ba.name == "Payroll Checking"
        assert ba.company_id == _COMPANY_ID
        assert ba.gl_account_id == _GL_ACCOUNT_ID

    def test_currency_column_default_is_usd(self) -> None:
        """Column-level default for currency must be 'USD'.

        SQLAlchemy applies Python-side column defaults at flush time (not at
        Python instantiation), so we verify the column metadata rather than
        the instance attribute.
        """
        col_default = BankAccount.__table__.c.currency.default
        assert col_default is not None
        assert col_default.arg == "USD"

    def test_active_column_default_is_true(self) -> None:
        """Column-level default for active must be True."""
        col_default = BankAccount.__table__.c.active.default
        assert col_default is not None
        assert col_default.arg is True

    def test_optional_fields_default_to_none(self) -> None:
        ba = BankAccount(
            company_id=_COMPANY_ID,
            gl_account_id=_GL_ACCOUNT_ID,
            name="Test",
        )
        assert ba.account_number is None
        assert ba.routing_number is None
        assert ba.bank_name is None

    def test_id_callable_default_generates_uuid(self) -> None:
        """The id column's callable default must produce unique UUIDs.

        SQLAlchemy evaluates the callable at flush time rather than at
        Python object creation, so we test the column default directly.
        SQLAlchemy wraps the callable in a one-arg shim (ctx), so we
        pass ``None`` as the context to invoke it.
        """
        col_default = BankAccount.__table__.c.id.default
        assert col_default is not None
        id1 = col_default.arg(None)
        id2 = col_default.arg(None)
        assert isinstance(id1, uuid.UUID)
        assert id1 != id2  # each call produces a unique value

    def test_repr_contains_name(self) -> None:
        ba = _make_bank_account(name="Savings")
        assert "Savings" in repr(ba)

    def test_repr_contains_active_flag(self) -> None:
        ba = _make_bank_account(active=False)
        assert "active=False" in repr(ba)


class TestBankAccountDomainHelpers:
    def test_deactivate(self) -> None:
        ba = _make_bank_account(active=True)
        ba.deactivate()
        assert ba.active is False

    def test_activate(self) -> None:
        ba = _make_bank_account(active=False)
        ba.activate()
        assert ba.active is True


# ===========================================================================
# Pydantic schema tests
# ===========================================================================


class TestBankAccountCreateSchema:
    def test_required_fields(self) -> None:
        from cairnbooks.api.bank_account import BankAccountCreate

        schema = BankAccountCreate(
            company_id=_COMPANY_ID,
            gl_account_id=_GL_ACCOUNT_ID,
            name="Checking",
        )
        assert schema.name == "Checking"

    def test_currency_defaults_to_usd(self) -> None:
        from cairnbooks.api.bank_account import BankAccountCreate

        schema = BankAccountCreate(
            company_id=_COMPANY_ID,
            gl_account_id=_GL_ACCOUNT_ID,
            name="Checking",
        )
        assert schema.currency == "USD"

    def test_active_defaults_to_true(self) -> None:
        from cairnbooks.api.bank_account import BankAccountCreate

        schema = BankAccountCreate(
            company_id=_COMPANY_ID,
            gl_account_id=_GL_ACCOUNT_ID,
            name="Checking",
        )
        assert schema.active is True


class TestBankAccountUpdateSchema:
    def test_all_fields_optional(self) -> None:
        from cairnbooks.api.bank_account import BankAccountUpdate

        # Must be instantiable with no arguments
        schema = BankAccountUpdate()
        assert schema.name is None
        assert schema.active is None
        assert schema.currency is None

    def test_model_dump_exclude_unset(self) -> None:
        from cairnbooks.api.bank_account import BankAccountUpdate

        schema = BankAccountUpdate(name="New Name")
        dumped = schema.model_dump(exclude_unset=True)
        assert "name" in dumped
        assert "active" not in dumped


class TestBankAccountReadSchema:
    def test_from_orm_object(self) -> None:
        from cairnbooks.api.bank_account import BankAccountRead

        ba = _make_bank_account()
        read = BankAccountRead.model_validate(ba)
        assert read.id == _BANK_ACCOUNT_ID
        assert read.name == "Main Checking"
        assert read.currency == "USD"
        assert read.active is True


# ===========================================================================
# API endpoint tests (TestClient + mocked AsyncSession)
# ===========================================================================


class TestCreateBankAccount:
    def test_create_returns_201(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        response = client.post(
            "/bank-accounts",
            json={
                "company_id": str(_COMPANY_ID),
                "gl_account_id": str(_GL_ACCOUNT_ID),
                "name": "Main Checking",
                "bank_name": "First National Bank",
                "currency": "USD",
            },
        )

        assert response.status_code == 201

    def test_create_response_body(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        response = client.post(
            "/bank-accounts",
            json={
                "company_id": str(_COMPANY_ID),
                "gl_account_id": str(_GL_ACCOUNT_ID),
                "name": "Main Checking",
            },
        )
        data = response.json()
        assert data["name"] == "Main Checking"
        assert data["currency"] == "USD"
        assert data["active"] is True
        assert "id" in data

    def test_create_calls_session_add(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        client.post(
            "/bank-accounts",
            json={
                "company_id": str(_COMPANY_ID),
                "gl_account_id": str(_GL_ACCOUNT_ID),
                "name": "Payroll",
            },
        )
        mock_session.add.assert_called_once()

    def test_create_missing_required_field_returns_422(self) -> None:
        mock_session = _make_mock_session()
        client = _make_test_client(mock_session)

        # Missing name
        response = client.post(
            "/bank-accounts",
            json={
                "company_id": str(_COMPANY_ID),
                "gl_account_id": str(_GL_ACCOUNT_ID),
            },
        )
        assert response.status_code == 422


class TestListBankAccounts:
    def test_list_returns_200(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_accounts=[ba])
        client = _make_test_client(mock_session)

        response = client.get("/bank-accounts")
        assert response.status_code == 200

    def test_list_returns_array(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_accounts=[ba])
        client = _make_test_client(mock_session)

        response = client.get("/bank-accounts")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Main Checking"

    def test_list_empty_returns_empty_array(self) -> None:
        mock_session = _make_mock_session(bank_accounts=[])
        client = _make_test_client(mock_session)

        response = client.get("/bank-accounts")
        assert response.json() == []

    def test_list_with_company_id_filter(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_accounts=[ba])
        client = _make_test_client(mock_session)

        response = client.get(f"/bank-accounts?company_id={_COMPANY_ID}")
        assert response.status_code == 200

    def test_list_active_only_filter(self) -> None:
        ba = _make_bank_account(active=True)
        mock_session = _make_mock_session(bank_accounts=[ba])
        client = _make_test_client(mock_session)

        response = client.get("/bank-accounts?active_only=true")
        assert response.status_code == 200


class TestGetBankAccount:
    def test_get_existing_returns_200(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        response = client.get(f"/bank-accounts/{_BANK_ACCOUNT_ID}")
        assert response.status_code == 200

    def test_get_existing_returns_correct_data(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        response = client.get(f"/bank-accounts/{_BANK_ACCOUNT_ID}")
        data = response.json()
        assert data["id"] == str(_BANK_ACCOUNT_ID)
        assert data["name"] == "Main Checking"
        assert data["routing_number"] == "021000021"

    def test_get_missing_returns_404(self) -> None:
        mock_session = _make_mock_session(bank_account=None)
        client = _make_test_client(mock_session)

        missing_id = uuid.uuid4()
        response = client.get(f"/bank-accounts/{missing_id}")
        assert response.status_code == 404

    def test_get_404_contains_detail(self) -> None:
        mock_session = _make_mock_session(bank_account=None)
        client = _make_test_client(mock_session)

        missing_id = uuid.uuid4()
        response = client.get(f"/bank-accounts/{missing_id}")
        assert "not found" in response.json()["detail"].lower()


class TestUpdateBankAccount:
    def test_patch_existing_returns_200(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        response = client.patch(
            f"/bank-accounts/{_BANK_ACCOUNT_ID}",
            json={"name": "Updated Checking"},
        )
        assert response.status_code == 200

    def test_patch_applies_name_change(self) -> None:
        ba = _make_bank_account(name="Old Name")
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        response = client.patch(
            f"/bank-accounts/{_BANK_ACCOUNT_ID}",
            json={"name": "New Name"},
        )
        # The route mutates ba in-place via setattr, so the serialized
        # response should reflect the new name.
        data = response.json()
        assert data["name"] == "New Name"

    def test_patch_deactivate(self) -> None:
        ba = _make_bank_account(active=True)
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        response = client.patch(
            f"/bank-accounts/{_BANK_ACCOUNT_ID}",
            json={"active": False},
        )
        assert response.status_code == 200
        assert response.json()["active"] is False

    def test_patch_empty_body_returns_200(self) -> None:
        """PATCH with no fields is a valid no-op."""
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        response = client.patch(f"/bank-accounts/{_BANK_ACCOUNT_ID}", json={})
        assert response.status_code == 200

    def test_patch_missing_returns_404(self) -> None:
        mock_session = _make_mock_session(bank_account=None)
        client = _make_test_client(mock_session)

        missing_id = uuid.uuid4()
        response = client.patch(f"/bank-accounts/{missing_id}", json={"name": "X"})
        assert response.status_code == 404


class TestDeleteBankAccount:
    def test_delete_existing_returns_204(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        response = client.delete(f"/bank-accounts/{_BANK_ACCOUNT_ID}")
        assert response.status_code == 204

    def test_delete_calls_session_delete(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        client.delete(f"/bank-accounts/{_BANK_ACCOUNT_ID}")
        mock_session.delete.assert_called_once_with(ba)

    def test_delete_missing_returns_404(self) -> None:
        mock_session = _make_mock_session(bank_account=None)
        client = _make_test_client(mock_session)

        missing_id = uuid.uuid4()
        response = client.delete(f"/bank-accounts/{missing_id}")
        assert response.status_code == 404

    def test_delete_response_body_is_empty(self) -> None:
        ba = _make_bank_account()
        mock_session = _make_mock_session(bank_account=ba)
        client = _make_test_client(mock_session)

        response = client.delete(f"/bank-accounts/{_BANK_ACCOUNT_ID}")
        assert response.content == b""
