"""Unit tests for the Tenant and Company SQLAlchemy models.

Uses an in-memory SQLite database so no live PostgreSQL instance is required.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - side-effect: registers models with Base
from app.db import Base
from app.models.company import Company
from app.models.tenant import Tenant

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def engine():
    """SQLite in-memory engine with schema created once per module."""
    _engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)
    _engine.dispose()


@pytest.fixture()
def session(engine):
    """Transactional session that rolls back after each test."""
    with Session(engine) as _session:
        yield _session
        _session.rollback()


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_tenant(slug_suffix: str = "") -> Tenant:
    return Tenant(
        id=uuid.uuid4(),
        name=f"Test Tenant {slug_suffix}",
        slug=f"test-tenant{slug_suffix}",
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_tenant_can_be_created(session: Session) -> None:
    """Tenant is persisted and retrieved correctly."""
    tenant = make_tenant("-1")
    session.add(tenant)
    session.flush()

    found = session.get(Tenant, tenant.id)
    assert found is not None
    assert found.name == "Test Tenant -1"
    assert found.slug == "test-tenant-1"


def test_company_can_be_created(session: Session) -> None:
    """Company is persisted with a valid Tenant foreign key."""
    tenant = make_tenant("-2")
    session.add(tenant)
    session.flush()

    company = Company(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Acme Books LLC",
        currency="USD",
        fiscal_year_start_month=1,
    )
    session.add(company)
    session.flush()

    found = session.get(Company, company.id)
    assert found is not None
    assert found.name == "Acme Books LLC"
    assert found.tenant_id == tenant.id
    assert found.currency == "USD"
    assert found.fiscal_year_start_month == 1


def test_company_tenant_relationship(session: Session) -> None:
    """Company.tenant back-reference resolves to the owning Tenant."""
    tenant = make_tenant("-3")
    session.add(tenant)
    session.flush()

    company = Company(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Gamma Books",
        currency="EUR",
        fiscal_year_start_month=4,
    )
    session.add(company)
    session.flush()

    assert company.tenant is not None
    assert company.tenant.slug == "test-tenant-3"


def test_tenant_has_companies_collection(session: Session) -> None:
    """Tenant.companies relationship lists all child companies."""
    tenant = make_tenant("-4")
    session.add(tenant)
    session.flush()

    for i in range(3):
        session.add(
            Company(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name=f"Company {i}",
                currency="GBP",
                fiscal_year_start_month=1,
            )
        )
    session.flush()
    session.refresh(tenant)

    assert len(tenant.companies) == 3  # type: ignore[arg-type]


def test_company_repr_contains_name(session: Session) -> None:
    """Company.__repr__ includes the company name for easy debugging."""
    tenant = make_tenant("-5")
    session.add(tenant)
    session.flush()

    company = Company(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Debug Co",
        currency="CAD",
        fiscal_year_start_month=7,
    )
    assert "Debug Co" in repr(company)
