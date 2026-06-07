"""Unit tests for the Account model and default COA seed function.

Uses an in-memory SQLite database so no live PostgreSQL instance is required.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - side-effect: registers all models with Base
from app.db import Base
from app.models.account import Account, AccountType, NormalBalance, default_normal_balance
from app.models.company import Company
from app.models.tenant import Tenant
from app.services.coa_seed import DEFAULT_COA_ENTRIES, seed_default_coa

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


def make_tenant(session: Session, slug_suffix: str = "") -> Tenant:
    tenant = Tenant(
        id=uuid.uuid4(),
        name=f"Test Tenant {slug_suffix}",
        slug=f"test-tenant-acct{slug_suffix}",
    )
    session.add(tenant)
    session.flush()
    return tenant


def make_company(session: Session, tenant: Tenant, suffix: str = "") -> Company:
    company = Company(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=f"Acme Books {suffix}",
        currency="USD",
        fiscal_year_start_month=1,
    )
    session.add(company)
    session.flush()
    return company


# ── AccountType & NormalBalance enum tests ────────────────────────────────────


def test_account_type_values() -> None:
    assert AccountType.ASSET.value == "asset"
    assert AccountType.LIABILITY.value == "liability"
    assert AccountType.EQUITY.value == "equity"
    assert AccountType.INCOME.value == "income"
    assert AccountType.EXPENSE.value == "expense"


def test_normal_balance_values() -> None:
    assert NormalBalance.DEBIT.value == "debit"
    assert NormalBalance.CREDIT.value == "credit"


@pytest.mark.parametrize(
    ("account_type", "expected"),
    [
        (AccountType.ASSET, NormalBalance.DEBIT),
        (AccountType.EXPENSE, NormalBalance.DEBIT),
        (AccountType.LIABILITY, NormalBalance.CREDIT),
        (AccountType.EQUITY, NormalBalance.CREDIT),
        (AccountType.INCOME, NormalBalance.CREDIT),
    ],
)
def test_default_normal_balance_convention(
    account_type: AccountType, expected: NormalBalance
) -> None:
    assert default_normal_balance(account_type) == expected


# ── Account model persistence ──────────────────────────────────────────────────


def test_account_can_be_created(session: Session) -> None:
    """An Account is persisted and retrieved correctly."""
    tenant = make_tenant(session, "-a1")
    company = make_company(session, tenant, "A1")

    acct = Account(
        id=uuid.uuid4(),
        company_id=company.id,
        code="1010",
        name="Checking Account",
        type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
    )
    session.add(acct)
    session.flush()

    found = session.get(Account, acct.id)
    assert found is not None
    assert found.code == "1010"
    assert found.name == "Checking Account"
    assert found.type == AccountType.ASSET
    assert found.normal_balance == NormalBalance.DEBIT
    assert found.company_id == company.id
    assert found.parent_id is None
    assert found.is_active is True


def test_account_parent_child_relationship(session: Session) -> None:
    """Accounts form a parent→children hierarchy."""
    tenant = make_tenant(session, "-a2")
    company = make_company(session, tenant, "A2")

    parent = Account(
        id=uuid.uuid4(),
        company_id=company.id,
        code="1000",
        name="Assets",
        type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
    )
    session.add(parent)
    session.flush()

    child = Account(
        id=uuid.uuid4(),
        company_id=company.id,
        parent_id=parent.id,
        code="1010",
        name="Checking",
        type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
    )
    session.add(child)
    session.flush()

    session.refresh(parent)
    assert child.parent_id == parent.id
    assert child.parent is not None
    assert child.parent.code == "1000"
    assert len(parent.children) == 1
    assert parent.children[0].code == "1010"


def test_account_company_relationship(session: Session) -> None:
    """Account.company back-reference resolves to the owning Company."""
    tenant = make_tenant(session, "-a3")
    company = make_company(session, tenant, "A3")

    acct = Account(
        id=uuid.uuid4(),
        company_id=company.id,
        code="4100",
        name="Sales Revenue",
        type=AccountType.INCOME,
        normal_balance=NormalBalance.CREDIT,
    )
    session.add(acct)
    session.flush()

    assert acct.company is not None
    assert acct.company.name == "Acme Books A3"


def test_company_accounts_collection(session: Session) -> None:
    """Company.accounts lists all child accounts."""
    tenant = make_tenant(session, "-a4")
    company = make_company(session, tenant, "A4")

    for code, name, atype in [
        ("5100", "COGS", AccountType.EXPENSE),
        ("5200", "Salaries", AccountType.EXPENSE),
        ("5300", "Rent", AccountType.EXPENSE),
    ]:
        session.add(
            Account(
                id=uuid.uuid4(),
                company_id=company.id,
                code=code,
                name=name,
                type=atype,
                normal_balance=NormalBalance.DEBIT,
            )
        )
    session.flush()
    session.refresh(company)

    assert len(company.accounts) == 3


def test_account_code_unique_per_company(session: Session) -> None:
    """Two accounts with the same code under the same company violate uniqueness."""
    from sqlalchemy.exc import IntegrityError

    tenant = make_tenant(session, "-a5")
    company = make_company(session, tenant, "A5")

    session.add(
        Account(
            id=uuid.uuid4(),
            company_id=company.id,
            code="1000",
            name="Assets",
            type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
        )
    )
    session.flush()

    session.add(
        Account(
            id=uuid.uuid4(),
            company_id=company.id,
            code="1000",  # duplicate!
            name="Assets Duplicate",
            type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_same_code_allowed_for_different_companies(session: Session) -> None:
    """The same account code may appear in two different companies."""
    tenant = make_tenant(session, "-a6")
    c1 = make_company(session, tenant, "A6a")
    c2 = make_company(session, tenant, "A6b")

    session.add(
        Account(
            id=uuid.uuid4(),
            company_id=c1.id,
            code="1000",
            name="Assets",
            type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
        )
    )
    session.add(
        Account(
            id=uuid.uuid4(),
            company_id=c2.id,
            code="1000",
            name="Assets",
            type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
        )
    )
    session.flush()  # should not raise


def test_account_repr(session: Session) -> None:
    """Account.__repr__ includes key identifiers."""
    acct = Account(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        code="9999",
        name="Test Account",
        type=AccountType.LIABILITY,
        normal_balance=NormalBalance.CREDIT,
    )
    r = repr(acct)
    assert "9999" in r
    assert "Test Account" in r
    assert "liability" in r


def test_contra_asset_uses_credit_normal_balance(session: Session) -> None:
    """A contra-asset account (e.g. Accumulated Depreciation) has credit normal balance."""
    tenant = make_tenant(session, "-a7")
    company = make_company(session, tenant, "A7")

    contra = Account(
        id=uuid.uuid4(),
        company_id=company.id,
        code="1520",
        name="Accumulated Depreciation",
        type=AccountType.ASSET,
        normal_balance=NormalBalance.CREDIT,  # explicitly overridden
    )
    session.add(contra)
    session.flush()

    found = session.get(Account, contra.id)
    assert found is not None
    assert found.type == AccountType.ASSET
    assert found.normal_balance == NormalBalance.CREDIT


# ── COA seed tests ────────────────────────────────────────────────────────────


def test_seed_creates_accounts(session: Session) -> None:
    """seed_default_coa returns a non-empty list of created accounts."""
    tenant = make_tenant(session, "-s1")
    company = make_company(session, tenant, "S1")

    created = seed_default_coa(session, company.id)

    assert len(created) > 0


def test_seed_covers_all_five_types(session: Session) -> None:
    """The seed produces at least one account of each fundamental type."""
    tenant = make_tenant(session, "-s2")
    company = make_company(session, tenant, "S2")

    seed_default_coa(session, company.id)

    all_accounts = session.scalars(select(Account).where(Account.company_id == company.id)).all()
    types_found = {a.type for a in all_accounts}

    assert AccountType.ASSET in types_found
    assert AccountType.LIABILITY in types_found
    assert AccountType.EQUITY in types_found
    assert AccountType.INCOME in types_found
    assert AccountType.EXPENSE in types_found


def test_seed_parent_child_links(session: Session) -> None:
    """Child accounts reference their parent via parent_id."""
    tenant = make_tenant(session, "-s3")
    company = make_company(session, tenant, "S3")

    seed_default_coa(session, company.id)

    # "1110 Checking Account" should have parent "1100 Cash and Cash Equivalents"
    checking = session.scalars(
        select(Account).where(Account.company_id == company.id, Account.code == "1110")
    ).first()
    assert checking is not None
    assert checking.parent_id is not None

    cash_eq = session.scalars(
        select(Account).where(Account.company_id == company.id, Account.code == "1100")
    ).first()
    assert cash_eq is not None
    assert checking.parent_id == cash_eq.id


def test_seed_is_idempotent(session: Session) -> None:
    """Calling seed_default_coa twice does not duplicate accounts."""
    tenant = make_tenant(session, "-s4")
    company = make_company(session, tenant, "S4")

    created_first = seed_default_coa(session, company.id)
    created_second = seed_default_coa(session, company.id)

    assert len(created_second) == 0  # nothing new created on second call

    total = session.scalars(select(Account).where(Account.company_id == company.id)).all()
    assert len(total) == len(created_first)


def test_seed_normal_balances_follow_convention(session: Session) -> None:
    """Standard accounts use the conventional normal balance for their type."""
    tenant = make_tenant(session, "-s5")
    company = make_company(session, tenant, "S5")

    seed_default_coa(session, company.id)

    accounts = session.scalars(select(Account).where(Account.company_id == company.id)).all()

    # Every account whose code does NOT represent a contra account should
    # have the conventional normal balance.  Contra accounts in the seed
    # are 1520 (Accumulated Depreciation) and 3300 (Owner's Draw).
    CONTRA_CODES = {"1520", "3300"}

    for acct in accounts:
        if acct.code in CONTRA_CODES:
            continue  # contra accounts intentionally differ
        expected = default_normal_balance(acct.type)
        assert acct.normal_balance == expected, (
            f"Account {acct.code!r} ({acct.type.value}) has "
            f"normal_balance={acct.normal_balance.value!r}, expected {expected.value!r}"
        )


def test_default_coa_entries_flat_list() -> None:
    """DEFAULT_COA_ENTRIES provides a flat list of all seed accounts."""
    assert len(DEFAULT_COA_ENTRIES) > 0
    codes = {e["code"] for e in DEFAULT_COA_ENTRIES}
    # Spot-check a few required codes
    assert "1000" in codes
    assert "2110" in codes  # Accounts Payable
    assert "4100" in codes  # Sales Revenue
    assert "5200" in codes  # Salaries and Wages
    # Every entry has required keys
    for entry in DEFAULT_COA_ENTRIES:
        assert "code" in entry
        assert "name" in entry
        assert "type" in entry
