"""Tests for the Item CRUD API and Item ORM model.

Structure
---------
1. **ORM metadata tests** (``TestItemORM``)
   Pure-Python, no database connection, no I/O.  Verifies columns,
   constraints, foreign keys, and index declarations.

2. **API endpoint tests** (``TestItemAPI``)
   Uses :class:`starlette.testclient.TestClient` with the database
   session overridden by a lightweight in-process stub so these tests
   run without a real PostgreSQL instance.

   Each test sets up the stub's return values then exercises the full
   FastAPI route handler, validating HTTP status codes and JSON bodies.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from starlette.testclient import TestClient

from cairnbooks.app import create_app
from cairnbooks.db import Base, get_db
from cairnbooks.models.item import Item

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_COMPANY_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
_ITEM_ID = uuid.UUID("20000000-0000-0000-0000-000000000002")
_INCOME_ID = uuid.UUID("30000000-0000-0000-0000-000000000003")
_EXPENSE_ID = uuid.UUID("40000000-0000-0000-0000-000000000004")
_NOW = datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC)


def _make_item(**overrides: Any) -> Item:
    """Return a pre-populated :class:`Item` for use in assertions."""
    item = Item(
        company_id=_COMPANY_ID,
        name="Widget Pro",
        description="A professional widget",
        income_account_id=_INCOME_ID,
        expense_account_id=_EXPENSE_ID,
        active=True,
    )
    item.id = _ITEM_ID
    item.created_at = _NOW
    item.updated_at = _NOW
    for k, v in overrides.items():
        setattr(item, k, v)
    return item


# ---------------------------------------------------------------------------
# Fake async session
# ---------------------------------------------------------------------------


class _FakeScalars:
    """Minimal stand-in for SQLAlchemy's ``ScalarResult``."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _FakeResult:
    """Stand-in for SQLAlchemy's ``CursorResult`` / ``ChunkedIteratorResult``."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)

    def scalar_one_or_none(self) -> Any:
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Minimal async session stub used in dependency overrides.

    Usage::

        session = _FakeSession()
        session.set_result([item])          # prime execute() return value
        # ...configure app override, run request...
        assert session.added == [item]
    """

    def __init__(self) -> None:
        self._result: list[Any] = []
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self._flushed = False

    def set_result(self, rows: list[Any]) -> None:
        self._result = rows

    # ── Async session protocol ──────────────────────────────────────────

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self._flushed = True

    async def refresh(self, obj: Any) -> None:
        # Ensure timestamps / id are present (they are set by default=… callables)
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid.uuid4()
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = _NOW
        if not hasattr(obj, "updated_at") or obj.updated_at is None:
            obj.updated_at = _NOW

    async def execute(self, stmt: Any) -> _FakeResult:  # noqa: ARG002
        return _FakeResult(self._result)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


# ---------------------------------------------------------------------------
# TestClient factory — injects a fresh FakeSession per test
# ---------------------------------------------------------------------------


def _make_client(session: _FakeSession) -> TestClient:
    """Return a :class:`TestClient` with ``get_db`` replaced by *session*."""
    app = create_app()

    async def _override() -> Any:
        yield session

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


# ===========================================================================
# 1. ORM metadata (pure unit — no DB)
# ===========================================================================


class TestItemORM:
    """Verify the Item ORM is wired correctly without touching a database."""

    def test_tablename(self) -> None:
        assert Item.__tablename__ == "items"

    def test_table_registered_in_base_metadata(self) -> None:
        assert "items" in Base.metadata.tables

    def test_required_columns_present(self) -> None:
        cols = {c.name for c in Item.__table__.columns}
        assert cols >= {
            "id",
            "company_id",
            "name",
            "description",
            "income_account_id",
            "expense_account_id",
            "active",
            "created_at",
            "updated_at",
        }

    def test_company_id_fk_targets_companies(self) -> None:
        col = Item.__table__.c["company_id"]
        targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "companies.id" in targets

    def test_income_account_id_fk_targets_accounts(self) -> None:
        col = Item.__table__.c["income_account_id"]
        targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "accounts.id" in targets

    def test_expense_account_id_fk_targets_accounts(self) -> None:
        col = Item.__table__.c["expense_account_id"]
        targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "accounts.id" in targets

    def test_company_id_not_nullable(self) -> None:
        assert Item.__table__.c["company_id"].nullable is False

    def test_name_not_nullable(self) -> None:
        assert Item.__table__.c["name"].nullable is False

    def test_description_nullable(self) -> None:
        assert Item.__table__.c["description"].nullable is True

    def test_income_account_id_nullable(self) -> None:
        assert Item.__table__.c["income_account_id"].nullable is True

    def test_expense_account_id_nullable(self) -> None:
        assert Item.__table__.c["expense_account_id"].nullable is True

    def test_active_not_nullable(self) -> None:
        assert Item.__table__.c["active"].nullable is False

    def test_active_has_server_default_true(self) -> None:
        # active's server_default is "true" (applied at INSERT time by PostgreSQL)
        col = Item.__table__.c["active"]
        assert col.server_default is not None
        assert "true" in str(col.server_default.arg).lower()

    def test_id_has_callable_column_default(self) -> None:
        # id's Python-side default must be a callable (uuid.uuid4)
        from sqlalchemy.sql.schema import CallableColumnDefault

        col_default = Item.__table__.c["id"].default
        assert col_default is not None
        assert isinstance(col_default, CallableColumnDefault)

    def test_composite_index_declared(self) -> None:
        index_names = {idx.name for idx in Item.__table__.indexes}
        assert "ix_items_company_active" in index_names

    def test_fk_company_id_on_delete_cascade(self) -> None:
        col = Item.__table__.c["company_id"]
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete.upper() == "CASCADE"

    def test_fk_income_account_set_null(self) -> None:
        col = Item.__table__.c["income_account_id"]
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete.upper() == "SET NULL"

    def test_fk_expense_account_set_null(self) -> None:
        col = Item.__table__.c["expense_account_id"]
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete.upper() == "SET NULL"

    def test_repr_includes_name(self) -> None:
        item = _make_item()
        assert "Widget Pro" in repr(item)

    def test_repr_includes_active(self) -> None:
        item = _make_item()
        assert "active=True" in repr(item)


# ===========================================================================
# 2. API endpoint tests (mocked DB session)
# ===========================================================================


class TestCreateItem:
    """POST /companies/{company_id}/items"""

    def test_create_returns_201(self) -> None:
        session = _FakeSession()
        client = _make_client(session)
        payload = {
            "name": "Widget Pro",
            "description": "A professional widget",
            "income_account_id": str(_INCOME_ID),
            "expense_account_id": str(_EXPENSE_ID),
        }
        resp = client.post(f"/companies/{_COMPANY_ID}/items", json=payload)
        assert resp.status_code == 201

    def test_create_response_body_has_name(self) -> None:
        session = _FakeSession()
        client = _make_client(session)
        payload = {"name": "Gadget"}
        resp = client.post(f"/companies/{_COMPANY_ID}/items", json=payload)
        assert resp.json()["name"] == "Gadget"

    def test_create_response_has_company_id(self) -> None:
        session = _FakeSession()
        client = _make_client(session)
        payload = {"name": "Gadget"}
        resp = client.post(f"/companies/{_COMPANY_ID}/items", json=payload)
        assert resp.json()["company_id"] == str(_COMPANY_ID)

    def test_create_adds_item_to_session(self) -> None:
        session = _FakeSession()
        client = _make_client(session)
        client.post(f"/companies/{_COMPANY_ID}/items", json={"name": "Sprocket"})
        assert len(session.added) == 1
        assert isinstance(session.added[0], Item)

    def test_create_active_defaults_true(self) -> None:
        session = _FakeSession()
        client = _make_client(session)
        resp = client.post(f"/companies/{_COMPANY_ID}/items", json={"name": "Sprocket"})
        assert resp.json()["active"] is True

    def test_create_active_can_be_false(self) -> None:
        session = _FakeSession()
        client = _make_client(session)
        resp = client.post(
            f"/companies/{_COMPANY_ID}/items",
            json={"name": "Archived", "active": False},
        )
        assert resp.json()["active"] is False

    def test_create_with_account_ids(self) -> None:
        session = _FakeSession()
        client = _make_client(session)
        payload = {
            "name": "Service",
            "income_account_id": str(_INCOME_ID),
            "expense_account_id": str(_EXPENSE_ID),
        }
        resp = client.post(f"/companies/{_COMPANY_ID}/items", json=payload)
        data = resp.json()
        assert data["income_account_id"] == str(_INCOME_ID)
        assert data["expense_account_id"] == str(_EXPENSE_ID)

    def test_create_without_name_returns_422(self) -> None:
        session = _FakeSession()
        client = _make_client(session)
        resp = client.post(f"/companies/{_COMPANY_ID}/items", json={})
        assert resp.status_code == 422

    def test_create_empty_name_returns_422(self) -> None:
        session = _FakeSession()
        client = _make_client(session)
        resp = client.post(f"/companies/{_COMPANY_ID}/items", json={"name": ""})
        assert resp.status_code == 422

    def test_create_response_includes_id(self) -> None:
        session = _FakeSession()
        client = _make_client(session)
        resp = client.post(f"/companies/{_COMPANY_ID}/items", json={"name": "Bolt"})
        data = resp.json()
        assert "id" in data
        # id must be a valid UUID string
        uuid.UUID(data["id"])

    def test_create_response_includes_timestamps(self) -> None:
        session = _FakeSession()
        client = _make_client(session)
        resp = client.post(f"/companies/{_COMPANY_ID}/items", json={"name": "Nut"})
        data = resp.json()
        assert "created_at" in data
        assert "updated_at" in data


class TestListItems:
    """GET /companies/{company_id}/items"""

    def test_list_returns_200(self) -> None:
        session = _FakeSession()
        session.set_result([_make_item()])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items")
        assert resp.status_code == 200

    def test_list_returns_array(self) -> None:
        session = _FakeSession()
        session.set_result([_make_item()])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items")
        assert isinstance(resp.json(), list)

    def test_list_empty_when_no_items(self) -> None:
        session = _FakeSession()
        session.set_result([])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items")
        assert resp.json() == []

    def test_list_returns_item_fields(self) -> None:
        session = _FakeSession()
        session.set_result([_make_item()])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items")
        item = resp.json()[0]
        assert item["name"] == "Widget Pro"
        assert item["company_id"] == str(_COMPANY_ID)
        assert item["income_account_id"] == str(_INCOME_ID)
        assert item["expense_account_id"] == str(_EXPENSE_ID)

    def test_list_multiple_items(self) -> None:
        item1 = _make_item(name="Alpha")
        item2 = _make_item(name="Beta", id=uuid.uuid4())
        session = _FakeSession()
        session.set_result([item1, item2])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items")
        assert len(resp.json()) == 2

    def test_list_active_only_param_accepted(self) -> None:
        session = _FakeSession()
        session.set_result([_make_item()])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items?active_only=true")
        assert resp.status_code == 200


class TestGetItem:
    """GET /companies/{company_id}/items/{item_id}"""

    def test_get_existing_returns_200(self) -> None:
        session = _FakeSession()
        session.set_result([_make_item()])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}")
        assert resp.status_code == 200

    def test_get_returns_correct_item(self) -> None:
        session = _FakeSession()
        session.set_result([_make_item()])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}")
        assert resp.json()["id"] == str(_ITEM_ID)
        assert resp.json()["name"] == "Widget Pro"

    def test_get_missing_returns_404(self) -> None:
        session = _FakeSession()
        session.set_result([])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}")
        assert resp.status_code == 404

    def test_get_404_contains_detail(self) -> None:
        session = _FakeSession()
        session.set_result([])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}")
        assert "detail" in resp.json()

    def test_get_returns_account_ids(self) -> None:
        session = _FakeSession()
        session.set_result([_make_item()])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}")
        data = resp.json()
        assert data["income_account_id"] == str(_INCOME_ID)
        assert data["expense_account_id"] == str(_EXPENSE_ID)

    def test_get_item_with_no_accounts(self) -> None:
        session = _FakeSession()
        session.set_result([_make_item(income_account_id=None, expense_account_id=None)])
        client = _make_client(session)
        resp = client.get(f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["income_account_id"] is None
        assert data["expense_account_id"] is None


class TestUpdateItem:
    """PATCH /companies/{company_id}/items/{item_id}"""

    def test_update_existing_returns_200(self) -> None:
        item = _make_item()
        session = _FakeSession()
        session.set_result([item])
        client = _make_client(session)
        resp = client.patch(
            f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}",
            json={"name": "Widget Elite"},
        )
        assert resp.status_code == 200

    def test_update_changes_name(self) -> None:
        item = _make_item()
        session = _FakeSession()
        session.set_result([item])
        client = _make_client(session)
        client.patch(
            f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}",
            json={"name": "Widget Elite"},
        )
        assert item.name == "Widget Elite"

    def test_update_changes_active(self) -> None:
        item = _make_item()
        session = _FakeSession()
        session.set_result([item])
        client = _make_client(session)
        client.patch(
            f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}",
            json={"active": False},
        )
        assert item.active is False

    def test_update_changes_income_account(self) -> None:
        new_income = uuid.uuid4()
        item = _make_item()
        session = _FakeSession()
        session.set_result([item])
        client = _make_client(session)
        client.patch(
            f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}",
            json={"income_account_id": str(new_income)},
        )
        assert item.income_account_id == new_income

    def test_update_missing_returns_404(self) -> None:
        session = _FakeSession()
        session.set_result([])
        client = _make_client(session)
        resp = client.patch(
            f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}",
            json={"name": "Doesn't matter"},
        )
        assert resp.status_code == 404

    def test_update_partial_leaves_other_fields(self) -> None:
        item = _make_item()
        original_description = item.description
        session = _FakeSession()
        session.set_result([item])
        client = _make_client(session)
        client.patch(
            f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}",
            json={"name": "New Name"},
        )
        # description should be unchanged
        assert item.description == original_description

    def test_update_empty_body_returns_200(self) -> None:
        session = _FakeSession()
        session.set_result([_make_item()])
        client = _make_client(session)
        resp = client.patch(
            f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}",
            json={},
        )
        assert resp.status_code == 200

    def test_update_description_to_none(self) -> None:
        item = _make_item()
        session = _FakeSession()
        session.set_result([item])
        client = _make_client(session)
        client.patch(
            f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}",
            json={"description": None},
        )
        assert item.description is None


class TestDeleteItem:
    """DELETE /companies/{company_id}/items/{item_id}"""

    def test_delete_existing_returns_204(self) -> None:
        session = _FakeSession()
        session.set_result([_make_item()])
        client = _make_client(session)
        resp = client.delete(f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}")
        assert resp.status_code == 204

    def test_delete_calls_session_delete(self) -> None:
        item = _make_item()
        session = _FakeSession()
        session.set_result([item])
        client = _make_client(session)
        client.delete(f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}")
        assert item in session.deleted

    def test_delete_missing_returns_404(self) -> None:
        session = _FakeSession()
        session.set_result([])
        client = _make_client(session)
        resp = client.delete(f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}")
        assert resp.status_code == 404

    def test_delete_returns_no_body(self) -> None:
        session = _FakeSession()
        session.set_result([_make_item()])
        client = _make_client(session)
        resp = client.delete(f"/companies/{_COMPANY_ID}/items/{_ITEM_ID}")
        assert resp.content == b""
