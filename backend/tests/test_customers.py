"""Tests for the Customer CRUD service.

These tests exercise each service function in isolation using a lightweight
stub for :class:`sqlalchemy.ext.asyncio.AsyncSession`.  No database connection
is required — all I/O is intercepted by :mod:`unittest.mock`.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.customer import Customer
from app.workflow import customers as svc


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

TENANT_ID: uuid.UUID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
COMPANY_ID: uuid.UUID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
CUSTOMER_ID: uuid.UUID = uuid.UUID("cccccccc-0000-0000-0000-000000000003")


def _make_customer(**overrides) -> Customer:
    """Build a transient (not session-attached) Customer via the ORM constructor.

    Using the proper constructor ensures SQLAlchemy's ``_sa_instance_state``
    is initialised, so attribute setters work correctly in tests.
    """
    defaults: dict = {
        "id": CUSTOMER_ID,
        "tenant_id": TENANT_ID,
        "company_id": COMPANY_ID,
        "name": "Acme Corp",
        "email": "billing@acme.example",
        "phone": "+1 555 0100",
        "is_active": True,
    }
    defaults.update(overrides)
    return Customer(**defaults)


def _mock_db() -> AsyncMock:
    """Return a minimal AsyncSession stub with synchronous ``add``."""
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _db_returning(row) -> AsyncMock:
    """Return a stub session whose ``execute`` resolves to *row* via scalar_one_or_none."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = row
    db = _mock_db()
    db.execute = AsyncMock(return_value=result_mock)
    return db


def _db_returning_many(rows: list) -> AsyncMock:
    """Return a stub session whose ``execute`` resolves to *rows* via scalars().all()."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    db = _mock_db()
    db.execute = AsyncMock(return_value=result_mock)
    return db


# ---------------------------------------------------------------------------
# create_customer
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_returns_customer_instance() -> None:
    db = _mock_db()

    result = await svc.create_customer(
        db,
        tenant_id=TENANT_ID,
        company_id=COMPANY_ID,
        name="Acme Corp",
        email="billing@acme.example",
        phone="+1 555 0100",
    )

    assert isinstance(result, Customer)
    assert result.name == "Acme Corp"
    assert result.email == "billing@acme.example"
    assert result.phone == "+1 555 0100"
    assert result.tenant_id == TENANT_ID
    assert result.company_id == COMPANY_ID
    assert result.is_active is True


@pytest.mark.anyio
async def test_create_flushes_session() -> None:
    db = _mock_db()

    customer = await svc.create_customer(
        db,
        tenant_id=TENANT_ID,
        company_id=COMPANY_ID,
        name="Flush Test Co",
    )

    db.add.assert_called_once_with(customer)
    db.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_create_without_optional_fields() -> None:
    db = _mock_db()

    customer = await svc.create_customer(
        db,
        tenant_id=TENANT_ID,
        company_id=COMPANY_ID,
        name="Minimal Co",
    )

    assert customer.email is None
    assert customer.phone is None


@pytest.mark.anyio
async def test_create_assigns_unique_ids() -> None:
    db = _mock_db()

    c1 = await svc.create_customer(db, tenant_id=TENANT_ID, company_id=COMPANY_ID, name="A")
    c2 = await svc.create_customer(db, tenant_id=TENANT_ID, company_id=COMPANY_ID, name="B")

    assert c1.id != c2.id


# ---------------------------------------------------------------------------
# get_customer
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_returns_customer_when_found() -> None:
    expected = _make_customer()
    db = _db_returning(expected)

    found = await svc.get_customer(db, tenant_id=TENANT_ID, customer_id=CUSTOMER_ID)

    assert found is expected
    db.execute.assert_awaited_once()


@pytest.mark.anyio
async def test_get_returns_none_when_not_found() -> None:
    db = _db_returning(None)

    found = await svc.get_customer(db, tenant_id=TENANT_ID, customer_id=uuid.uuid4())

    assert found is None


@pytest.mark.anyio
async def test_get_returns_none_for_wrong_tenant() -> None:
    # Session returns nothing because the WHERE clause excluded it — simulate None.
    db = _db_returning(None)

    found = await svc.get_customer(
        db, tenant_id=uuid.uuid4(), customer_id=CUSTOMER_ID
    )

    assert found is None


# ---------------------------------------------------------------------------
# list_customers
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_returns_active_customers_by_default() -> None:
    customers = [_make_customer(), _make_customer(id=uuid.uuid4(), name="Beta LLC")]
    db = _db_returning_many(customers)

    found = await svc.list_customers(db, tenant_id=TENANT_ID, company_id=COMPANY_ID)

    assert found == customers
    db.execute.assert_awaited_once()


@pytest.mark.anyio
async def test_list_include_inactive_does_not_filter() -> None:
    inactive = _make_customer(is_active=False)
    db = _db_returning_many([inactive])

    found = await svc.list_customers(
        db, tenant_id=TENANT_ID, company_id=COMPANY_ID, include_inactive=True
    )

    assert found == [inactive]


@pytest.mark.anyio
async def test_list_returns_empty_sequence_when_none() -> None:
    db = _db_returning_many([])

    found = await svc.list_customers(db, tenant_id=TENANT_ID, company_id=COMPANY_ID)

    assert list(found) == []


# ---------------------------------------------------------------------------
# update_customer
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_applies_name_change() -> None:
    existing = _make_customer(name="Old Name")
    db = _db_returning(existing)

    updated = await svc.update_customer(
        db,
        tenant_id=TENANT_ID,
        customer_id=CUSTOMER_ID,
        name="New Name",
    )

    assert updated is existing
    assert updated.name == "New Name"
    db.add.assert_called_once_with(existing)
    db.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_update_applies_email_and_phone() -> None:
    existing = _make_customer()
    db = _db_returning(existing)

    updated = await svc.update_customer(
        db,
        tenant_id=TENANT_ID,
        customer_id=CUSTOMER_ID,
        email="new@example.com",
        phone="+44 20 7946 0958",
    )

    assert updated.email == "new@example.com"
    assert updated.phone == "+44 20 7946 0958"


@pytest.mark.anyio
async def test_update_skips_none_fields() -> None:
    """Fields not explicitly passed must remain unchanged."""
    existing = _make_customer(name="Original", phone="+1 555 9999")
    db = _db_returning(existing)

    updated = await svc.update_customer(
        db,
        tenant_id=TENANT_ID,
        customer_id=CUSTOMER_ID,
        phone="+1 555 1234",
        # name and email not passed — must be preserved
    )

    assert updated.name == "Original"
    assert updated.phone == "+1 555 1234"


@pytest.mark.anyio
async def test_update_returns_none_when_not_found() -> None:
    db = _db_returning(None)

    result = await svc.update_customer(
        db,
        tenant_id=TENANT_ID,
        customer_id=uuid.uuid4(),
        name="Ghost",
    )

    assert result is None
    db.add.assert_not_called()
    db.flush.assert_not_awaited()


# ---------------------------------------------------------------------------
# deactivate_customer
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_deactivate_sets_is_active_false() -> None:
    existing = _make_customer(is_active=True)
    db = _db_returning(existing)

    result = await svc.deactivate_customer(
        db, tenant_id=TENANT_ID, customer_id=CUSTOMER_ID
    )

    assert result is existing
    assert result.is_active is False
    db.add.assert_called_once_with(existing)
    db.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_deactivate_returns_none_when_not_found() -> None:
    db = _db_returning(None)

    result = await svc.deactivate_customer(
        db, tenant_id=TENANT_ID, customer_id=uuid.uuid4()
    )

    assert result is None
    db.add.assert_not_called()
    db.flush.assert_not_awaited()


@pytest.mark.anyio
async def test_deactivate_is_idempotent() -> None:
    """Deactivating an already-inactive customer must not raise and must return it."""
    already_inactive = _make_customer(is_active=False)
    db = _db_returning(already_inactive)

    result = await svc.deactivate_customer(
        db, tenant_id=TENANT_ID, customer_id=CUSTOMER_ID
    )

    assert result is already_inactive
    assert result.is_active is False
