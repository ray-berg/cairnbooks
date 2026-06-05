"""Tests for the Vendor CRUD service.

The database session is replaced with an :class:`~unittest.mock.AsyncMock` so
these tests run without a real PostgreSQL instance.

Strategy
--------
- :func:`~app.services.vendor.create_vendor` — verify the correct
  :class:`~app.domain.vendor.Vendor` is constructed, added to the session,
  and flushed.
- :func:`~app.services.vendor.get_vendor` — verify the SELECT is executed and
  the result is unwrapped via ``scalar_one_or_none()``.
- :func:`~app.services.vendor.list_vendors` — verify results are returned as a
  list, ordered by name.
- :func:`~app.services.vendor.update_vendor` — verify only supplied fields are
  modified; verify ``None`` is returned for a missing vendor; verify
  :class:`ValueError` is raised for unknown fields.
- :func:`~app.services.vendor.delete_vendor` — verify the vendor is deleted
  and ``True`` returned; verify ``False`` returned when not found.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.vendor import Vendor
from app.services.vendor import (
    create_vendor,
    delete_vendor,
    get_vendor,
    list_vendors,
    update_vendor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT_ID = uuid.uuid4()
VENDOR_ID = uuid.uuid4()


def _make_vendor(**kwargs: object) -> Vendor:
    """Build a minimal :class:`Vendor` without hitting the database.

    Uses the regular ORM constructor so that SQLAlchemy instrumentation
    (``_sa_instance_state``) is correctly initialised.
    """
    defaults: dict = {
        "id": VENDOR_ID,
        "tenant_id": TENANT_ID,
        "name": "Acme Supplies",
        "email": None,
        "phone": None,
        "website": None,
        "address_line1": None,
        "address_line2": None,
        "city": None,
        "state": None,
        "postal_code": None,
        "country": None,
    }
    defaults.update(kwargs)
    return Vendor(**defaults)


def _mock_db() -> AsyncMock:
    """Return an async mock that mimics :class:`~sqlalchemy.ext.asyncio.AsyncSession`."""
    db = AsyncMock()
    db.add = MagicMock()  # synchronous
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    return db


def _stub_execute(db: AsyncMock, scalar_value: object) -> None:
    """Make ``db.execute()`` return a result whose scalar methods yield *scalar_value*."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_value
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = scalar_value if isinstance(scalar_value, list) else []
    result.scalars.return_value = scalars_mock
    db.execute.return_value = result


# ---------------------------------------------------------------------------
# create_vendor
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_create_vendor_returns_vendor() -> None:
    db = _mock_db()
    vendor = await create_vendor(db, tenant_id=TENANT_ID, name="Acme Supplies")

    assert isinstance(vendor, Vendor)
    assert vendor.name == "Acme Supplies"
    assert vendor.tenant_id == TENANT_ID


@pytest.mark.anyio
async def test_create_vendor_adds_to_session() -> None:
    db = _mock_db()
    vendor = await create_vendor(db, tenant_id=TENANT_ID, name="Acme Supplies")

    db.add.assert_called_once_with(vendor)


@pytest.mark.anyio
async def test_create_vendor_flushes_session() -> None:
    db = _mock_db()
    await create_vendor(db, tenant_id=TENANT_ID, name="Acme Supplies")

    db.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_create_vendor_stores_optional_fields() -> None:
    db = _mock_db()
    vendor = await create_vendor(
        db,
        tenant_id=TENANT_ID,
        name="Builders Ltd",
        email="info@builders.example",
        phone="+1-555-0100",
        website="https://builders.example",
        address_line1="123 Main St",
        address_line2="Suite 4",
        city="Springfield",
        state="IL",
        postal_code="62701",
        country="US",
    )

    assert vendor.email == "info@builders.example"
    assert vendor.phone == "+1-555-0100"
    assert vendor.website == "https://builders.example"
    assert vendor.address_line1 == "123 Main St"
    assert vendor.address_line2 == "Suite 4"
    assert vendor.city == "Springfield"
    assert vendor.state == "IL"
    assert vendor.postal_code == "62701"
    assert vendor.country == "US"


@pytest.mark.anyio
async def test_create_vendor_generates_unique_ids() -> None:
    db = _mock_db()
    v1 = await create_vendor(db, tenant_id=TENANT_ID, name="Vendor A")
    v2 = await create_vendor(db, tenant_id=TENANT_ID, name="Vendor B")

    assert v1.id != v2.id


# ---------------------------------------------------------------------------
# get_vendor
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_vendor_returns_vendor_when_found() -> None:
    db = _mock_db()
    expected = _make_vendor()
    _stub_execute(db, expected)

    result = await get_vendor(db, tenant_id=TENANT_ID, vendor_id=VENDOR_ID)

    assert result is expected
    db.execute.assert_awaited_once()


@pytest.mark.anyio
async def test_get_vendor_returns_none_when_not_found() -> None:
    db = _mock_db()
    _stub_execute(db, None)

    result = await get_vendor(db, tenant_id=TENANT_ID, vendor_id=VENDOR_ID)

    assert result is None


# ---------------------------------------------------------------------------
# list_vendors
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_list_vendors_returns_list() -> None:
    db = _mock_db()
    vendors = [_make_vendor(name="Alpha"), _make_vendor(name="Beta")]
    _stub_execute(db, vendors)

    result = await list_vendors(db, tenant_id=TENANT_ID)

    assert isinstance(result, list)
    assert len(result) == 2


@pytest.mark.anyio
async def test_list_vendors_returns_empty_list_when_none() -> None:
    db = _mock_db()
    _stub_execute(db, [])

    result = await list_vendors(db, tenant_id=TENANT_ID)

    assert result == []


@pytest.mark.anyio
async def test_list_vendors_executes_query() -> None:
    db = _mock_db()
    _stub_execute(db, [])

    await list_vendors(db, tenant_id=TENANT_ID)

    db.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_vendor
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_update_vendor_modifies_fields() -> None:
    db = _mock_db()
    vendor = _make_vendor(name="Old Name")
    _stub_execute(db, vendor)

    result = await update_vendor(
        db,
        tenant_id=TENANT_ID,
        vendor_id=VENDOR_ID,
        name="New Name",
        email="new@example.com",
    )

    assert result is vendor
    assert vendor.name == "New Name"
    assert vendor.email == "new@example.com"


@pytest.mark.anyio
async def test_update_vendor_flushes_session() -> None:
    db = _mock_db()
    _stub_execute(db, _make_vendor())

    await update_vendor(db, tenant_id=TENANT_ID, vendor_id=VENDOR_ID, name="Updated")

    db.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_update_vendor_returns_none_when_not_found() -> None:
    db = _mock_db()
    _stub_execute(db, None)

    result = await update_vendor(
        db, tenant_id=TENANT_ID, vendor_id=VENDOR_ID, name="Ghost"
    )

    assert result is None
    db.flush.assert_not_awaited()


@pytest.mark.anyio
async def test_update_vendor_raises_for_unknown_field() -> None:
    db = _mock_db()

    with pytest.raises(ValueError, match="Unknown vendor field"):
        await update_vendor(
            db,
            tenant_id=TENANT_ID,
            vendor_id=VENDOR_ID,
            nonexistent_column="bad",
        )


@pytest.mark.anyio
async def test_update_vendor_does_not_touch_unspecified_fields() -> None:
    db = _mock_db()
    vendor = _make_vendor(name="Keep Me", phone="555-1234")
    _stub_execute(db, vendor)

    await update_vendor(db, tenant_id=TENANT_ID, vendor_id=VENDOR_ID, email="x@y.com")

    # name and phone should be untouched
    assert vendor.name == "Keep Me"
    assert vendor.phone == "555-1234"


# ---------------------------------------------------------------------------
# delete_vendor
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_delete_vendor_returns_true_when_found() -> None:
    db = _mock_db()
    _stub_execute(db, _make_vendor())

    result = await delete_vendor(db, tenant_id=TENANT_ID, vendor_id=VENDOR_ID)

    assert result is True


@pytest.mark.anyio
async def test_delete_vendor_calls_db_delete() -> None:
    db = _mock_db()
    vendor = _make_vendor()
    _stub_execute(db, vendor)

    await delete_vendor(db, tenant_id=TENANT_ID, vendor_id=VENDOR_ID)

    db.delete.assert_awaited_once_with(vendor)


@pytest.mark.anyio
async def test_delete_vendor_flushes_session() -> None:
    db = _mock_db()
    _stub_execute(db, _make_vendor())

    await delete_vendor(db, tenant_id=TENANT_ID, vendor_id=VENDOR_ID)

    db.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_delete_vendor_returns_false_when_not_found() -> None:
    db = _mock_db()
    _stub_execute(db, None)

    result = await delete_vendor(db, tenant_id=TENANT_ID, vendor_id=VENDOR_ID)

    assert result is False


@pytest.mark.anyio
async def test_delete_vendor_does_not_flush_when_not_found() -> None:
    db = _mock_db()
    _stub_execute(db, None)

    await delete_vendor(db, tenant_id=TENANT_ID, vendor_id=VENDOR_ID)

    db.flush.assert_not_awaited()
