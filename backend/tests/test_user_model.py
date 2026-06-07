"""Tests for User, Role, UserRole models and password-hashing utilities.

Uses an in-memory SQLite database so no live PostgreSQL instance is required.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — registers all models with Base
from app.db import Base
from app.models.role import Role, RoleName, seed_roles
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_role import UserRole
from app.security.passwords import hash_password, verify_password

# ── Engine / session fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def engine():
    """SQLite in-memory engine with the full schema created once per module."""
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


def make_tenant(suffix: str = "") -> Tenant:
    return Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}", slug=f"tenant{suffix}")


def make_user(email: str = "alice@example.com") -> User:
    return User(id=uuid.uuid4(), email=email, hashed_password=hash_password("s3cr3t"))


# ── Password-hashing tests ────────────────────────────────────────────────────


def test_hash_password_returns_string() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert isinstance(hashed, str)
    assert len(hashed) > 0


def test_hash_password_is_not_plaintext() -> None:
    plain = "my-secret-password"
    hashed = hash_password(plain)
    assert hashed != plain


def test_verify_password_correct() -> None:
    plain = "correct-horse-battery-staple"
    assert verify_password(plain, hash_password(plain)) is True


def test_verify_password_wrong() -> None:
    hashed = hash_password("right-password")
    assert verify_password("wrong-password", hashed) is False


def test_hash_password_unique_salts() -> None:
    """Two hashes of the same password should differ (different salts)."""
    plain = "same-password"
    assert hash_password(plain) != hash_password(plain)


# ── Role model tests ──────────────────────────────────────────────────────────


def test_role_can_be_created(session: Session) -> None:
    role = Role(id=uuid.uuid4(), name="custom-role")
    session.add(role)
    session.flush()

    found = session.get(Role, role.id)
    assert found is not None
    assert found.name == "custom-role"


def test_role_repr_contains_name(session: Session) -> None:
    role = Role(id=uuid.uuid4(), name="test-repr-role")
    assert "test-repr-role" in repr(role)


def test_role_name_enum_values() -> None:
    assert RoleName.admin.value == "admin"
    assert RoleName.accountant.value == "accountant"
    assert RoleName.viewer.value == "viewer"


# ── seed_roles tests ──────────────────────────────────────────────────────────


def test_seed_roles_creates_three_builtin_roles(session: Session) -> None:
    roles = seed_roles(session)
    assert len(roles) == 3
    names = {r.name for r in roles}
    assert names == {"admin", "accountant", "viewer"}


def test_seed_roles_is_idempotent(session: Session) -> None:
    """Calling seed_roles twice must not create duplicate rows."""
    first = seed_roles(session)
    second = seed_roles(session)
    assert len(first) == len(second) == 3
    # IDs must be the same objects (or at least same values)
    assert {r.id for r in first} == {r.id for r in second}


def test_seed_roles_descriptions_present(session: Session) -> None:
    roles = seed_roles(session)
    for role in roles:
        assert role.description is not None
        assert len(role.description) > 0


# ── User model tests ──────────────────────────────────────────────────────────


def test_user_can_be_created(session: Session) -> None:
    user = make_user("bob@example.com")
    session.add(user)
    session.flush()

    found = session.get(User, user.id)
    assert found is not None
    assert found.email == "bob@example.com"


def test_user_is_active_defaults_to_true(session: Session) -> None:
    user = make_user("carol@example.com")
    session.add(user)
    session.flush()

    assert user.is_active is True


def test_user_can_be_deactivated(session: Session) -> None:
    user = make_user("dave@example.com")
    user.is_active = False
    session.add(user)
    session.flush()

    found = session.get(User, user.id)
    assert found is not None
    assert found.is_active is False


def test_user_repr_contains_email(session: Session) -> None:
    user = make_user("repr@example.com")
    assert "repr@example.com" in repr(user)


def test_user_hashed_password_stored(session: Session) -> None:
    plain = "super-secret"
    user = User(id=uuid.uuid4(), email="eve@example.com", hashed_password=hash_password(plain))
    session.add(user)
    session.flush()

    found = session.get(User, user.id)
    assert found is not None
    assert verify_password(plain, found.hashed_password)


# ── UserRole association tests ────────────────────────────────────────────────


def test_user_role_assignment(session: Session) -> None:
    tenant = make_tenant("-ur1")
    session.add(tenant)
    session.flush()

    roles = seed_roles(session)
    admin_role = next(r for r in roles if r.name == "admin")

    user = make_user("frank@example.com")
    session.add(user)
    session.flush()

    ur = UserRole(user_id=user.id, role_id=admin_role.id, tenant_id=tenant.id)
    session.add(ur)
    session.flush()

    found = session.get(
        UserRole, {"user_id": user.id, "role_id": admin_role.id, "tenant_id": tenant.id}
    )
    assert found is not None


def test_user_role_relationship(session: Session) -> None:
    """UserRole.user and UserRole.role back-references resolve correctly."""
    tenant = make_tenant("-ur2")
    session.add(tenant)
    session.flush()

    roles = seed_roles(session)
    viewer_role = next(r for r in roles if r.name == "viewer")

    user = make_user("grace@example.com")
    session.add(user)
    session.flush()

    ur = UserRole(user_id=user.id, role_id=viewer_role.id, tenant_id=tenant.id)
    session.add(ur)
    session.flush()

    assert ur.user.email == "grace@example.com"
    assert ur.role.name == "viewer"


def test_user_has_user_roles_collection(session: Session) -> None:
    """User.user_roles lists all role assignments for that user."""
    tenant = make_tenant("-ur3")
    session.add(tenant)
    session.flush()

    roles = seed_roles(session)
    user = make_user("heidi@example.com")
    session.add(user)
    session.flush()

    for role in roles:
        session.add(UserRole(user_id=user.id, role_id=role.id, tenant_id=tenant.id))
    session.flush()
    session.refresh(user)

    assert len(user.user_roles) == 3  # admin + accountant + viewer


def test_user_role_repr(session: Session) -> None:
    tenant = make_tenant("-ur4")
    session.add(tenant)
    session.flush()

    roles = seed_roles(session)
    accountant_role = next(r for r in roles if r.name == "accountant")

    user = make_user("ivan@example.com")
    session.add(user)
    session.flush()

    ur = UserRole(user_id=user.id, role_id=accountant_role.id, tenant_id=tenant.id)
    r = repr(ur)
    assert "UserRole" in r
    assert str(user.id) in r
