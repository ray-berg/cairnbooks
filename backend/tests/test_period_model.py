"""Unit tests for the FiscalPeriod SQLAlchemy model.

Uses an in-memory SQLite database so no live PostgreSQL instance is required.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - side-effect: registers all models with Base
from app.db import Base
from app.models.company import Company
from app.models.period import FiscalPeriod, PeriodStatus
from app.models.tenant import Tenant

# ── Fixtures ──────────────────────────────────────────────────────────────────


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


def make_company(tenant: Tenant, suffix: str = "") -> Company:
    return Company(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=f"Test Company{suffix}",
        currency="USD",
        fiscal_year_start_month=1,
    )


def make_period(
    company: Company,
    name: str = "Q1 2026",
    start: date = date(2026, 1, 1),
    end: date = date(2026, 3, 31),
    status: PeriodStatus = PeriodStatus.OPEN,
) -> FiscalPeriod:
    return FiscalPeriod(
        id=uuid.uuid4(),
        company_id=company.id,
        name=name,
        start_date=start,
        end_date=end,
        status=status,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_period_can_be_created(session: Session) -> None:
    """FiscalPeriod is persisted and retrieved by primary key."""
    tenant = make_tenant("-p1")
    session.add(tenant)
    session.flush()

    company = make_company(tenant, "-p1")
    session.add(company)
    session.flush()

    period = make_period(company, name="FY 2026")
    session.add(period)
    session.flush()

    found = session.get(FiscalPeriod, period.id)
    assert found is not None
    assert found.name == "FY 2026"
    assert found.company_id == company.id
    assert found.start_date == date(2026, 1, 1)
    assert found.end_date == date(2026, 3, 31)


def test_period_default_status_is_open(session: Session) -> None:
    """A newly created FiscalPeriod has status OPEN by default."""
    tenant = make_tenant("-p2")
    session.add(tenant)
    session.flush()

    company = make_company(tenant, "-p2")
    session.add(company)
    session.flush()

    period = make_period(company, name="Q2 2026", start=date(2026, 4, 1), end=date(2026, 6, 30))
    session.add(period)
    session.flush()

    found = session.get(FiscalPeriod, period.id)
    assert found is not None
    assert found.status == PeriodStatus.OPEN


def test_period_status_can_be_closed(session: Session) -> None:
    """A FiscalPeriod status can be changed to CLOSED."""
    tenant = make_tenant("-p3")
    session.add(tenant)
    session.flush()

    company = make_company(tenant, "-p3")
    session.add(company)
    session.flush()

    period = make_period(
        company,
        name="Q3 2025",
        start=date(2025, 7, 1),
        end=date(2025, 9, 30),
        status=PeriodStatus.CLOSED,
    )
    session.add(period)
    session.flush()

    found = session.get(FiscalPeriod, period.id)
    assert found is not None
    assert found.status == PeriodStatus.CLOSED


def test_period_status_transition(session: Session) -> None:
    """FiscalPeriod status can be updated from OPEN to CLOSED in-place."""
    tenant = make_tenant("-p4")
    session.add(tenant)
    session.flush()

    company = make_company(tenant, "-p4")
    session.add(company)
    session.flush()

    period = make_period(company, name="Q4 2025", start=date(2025, 10, 1), end=date(2025, 12, 31))
    session.add(period)
    session.flush()

    assert period.status == PeriodStatus.OPEN

    period.status = PeriodStatus.CLOSED
    session.flush()
    session.refresh(period)

    assert period.status == PeriodStatus.CLOSED


def test_period_company_relationship(session: Session) -> None:
    """FiscalPeriod.company back-reference resolves to the owning Company."""
    tenant = make_tenant("-p5")
    session.add(tenant)
    session.flush()

    company = make_company(tenant, "-p5")
    session.add(company)
    session.flush()

    period = make_period(company, name="H1 2026", start=date(2026, 1, 1), end=date(2026, 6, 30))
    session.add(period)
    session.flush()

    assert period.company is not None
    assert period.company.id == company.id
    assert period.company.name == "Test Company-p5"


def test_company_fiscal_periods_collection(session: Session) -> None:
    """Company.fiscal_periods lists all associated FiscalPeriod rows."""
    tenant = make_tenant("-p6")
    session.add(tenant)
    session.flush()

    company = make_company(tenant, "-p6")
    session.add(company)
    session.flush()

    quarters = [
        make_period(company, f"Q{i} 2026", date(2026, i * 3 - 2, 1), date(2026, i * 3, 28))
        for i in range(1, 4)
    ]
    session.add_all(quarters)
    session.flush()
    session.refresh(company)

    assert len(company.fiscal_periods) == 3  # type: ignore[arg-type]


def test_period_cascade_delete_with_company(session: Session) -> None:
    """Deleting a Company also deletes its FiscalPeriod rows (CASCADE)."""
    tenant = make_tenant("-p7")
    session.add(tenant)
    session.flush()

    company = make_company(tenant, "-p7")
    session.add(company)
    session.flush()

    period = make_period(company, name="FY 2026 Delete Test")
    session.add(period)
    session.flush()

    period_id = period.id
    session.delete(company)
    session.flush()

    assert session.get(FiscalPeriod, period_id) is None


def test_period_repr_contains_name_and_status(session: Session) -> None:
    """FiscalPeriod.__repr__ includes name and status for easy debugging."""
    tenant = make_tenant("-p8")
    session.add(tenant)
    session.flush()

    company = make_company(tenant, "-p8")
    session.add(company)
    session.flush()

    period = make_period(company, name="Repr Period")
    r = repr(period)
    assert "Repr Period" in r
    assert "open" in r


def test_period_status_enum_values() -> None:
    """PeriodStatus enum has exactly the expected string values."""
    assert PeriodStatus.OPEN.value == "open"
    assert PeriodStatus.CLOSED.value == "closed"
    assert set(PeriodStatus) == {PeriodStatus.OPEN, PeriodStatus.CLOSED}
