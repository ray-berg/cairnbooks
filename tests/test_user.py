"""Tests for the User ORM model and bcrypt password utilities.

These tests are database-free: all assertions run against the ORM class
definition and the pure-Python hashing functions.

Coverage
--------
- :class:`cairnbooks.models.user.User` — table name, column declarations,
  defaults, check constraints, index, and repr.
- :func:`cairnbooks.security.passwords.hash_password` — produces a valid
  bcrypt hash that is distinct from the plain-text input.
- :func:`cairnbooks.security.passwords.verify_password` — returns ``True``
  for the correct password and ``False`` for any wrong password.
"""

from __future__ import annotations

import uuid

from cairnbooks.db import Base
from cairnbooks.models.user import DEFAULT_ROLE, VALID_ROLES, User
from cairnbooks.security.passwords import hash_password, verify_password

# ---------------------------------------------------------------------------
# Password hashing / verification
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self) -> None:
        """The returned hash must not equal the plain-text password."""
        plain = "MyS3cr3tP@ss!"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_hash_starts_with_bcrypt_prefix(self) -> None:
        """bcrypt hashes always begin with '$2b$' (or '$2a$' / '$2y$')."""
        hashed = hash_password("test-password")
        assert hashed.startswith("$2")

    def test_hash_is_string(self) -> None:
        """hash_password must return a str, not bytes."""
        result = hash_password("any-password")
        assert isinstance(result, str)

    def test_two_hashes_differ_for_same_password(self) -> None:
        """bcrypt uses a random salt, so two hashes of the same password differ."""
        pw = "same-password"
        assert hash_password(pw) != hash_password(pw)

    def test_verify_correct_password_returns_true(self) -> None:
        """verify_password must return True when the password matches."""
        plain = "correct-horse-battery-staple"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password_returns_false(self) -> None:
        """verify_password must return False for any wrong password."""
        hashed = hash_password("real-password")
        assert verify_password("wrong-password", hashed) is False

    def test_verify_empty_string_returns_false(self) -> None:
        """An empty string must not match a non-empty password hash."""
        hashed = hash_password("not-empty")
        assert verify_password("", hashed) is False

    def test_verify_returns_bool(self) -> None:
        """verify_password must return a proper bool, not a truthy value."""
        hashed = hash_password("password")
        result = verify_password("password", hashed)
        assert type(result) is bool  # noqa: E721

    def test_custom_rounds(self) -> None:
        """hash_password accepts a custom rounds parameter (use low value in tests)."""
        # rounds=4 is the minimum valid value for bcrypt — fast enough for CI.
        hashed = hash_password("rounds-test", rounds=4)
        assert verify_password("rounds-test", hashed) is True
        assert "$2b$04$" in hashed


# ---------------------------------------------------------------------------
# User ORM model
# ---------------------------------------------------------------------------


class TestUserModel:
    def test_tablename(self) -> None:
        """User must map to the 'users' table."""
        assert User.__tablename__ == "users"

    def test_table_registered_on_metadata(self) -> None:
        """The 'users' table must appear in Base.metadata."""
        assert "users" in Base.metadata.tables

    def test_instantiate_with_required_fields(self) -> None:
        """User can be constructed with email and password_hash."""
        pw_hash = hash_password("password", rounds=4)
        user = User(email="alice@example.com", password_hash=pw_hash)
        assert user.email == "alice@example.com"
        assert user.password_hash == pw_hash

    def test_role_defaults_to_viewer(self) -> None:
        """User.role column default must be 'viewer'."""
        col_default = User.__table__.c.role.default
        assert col_default is not None
        assert col_default.arg == DEFAULT_ROLE
        assert DEFAULT_ROLE == "viewer"

    def test_valid_roles_set(self) -> None:
        """VALID_ROLES must contain the three expected roles."""
        assert VALID_ROLES == {"admin", "bookkeeper", "viewer"}

    def test_id_has_callable_default(self) -> None:
        """User.id must have a Python-side callable default (uuid.uuid4)."""
        from sqlalchemy.sql.schema import CallableColumnDefault

        col_default = User.__table__.c.id.default
        assert col_default is not None
        assert isinstance(col_default, CallableColumnDefault)
        assert isinstance(uuid.uuid4(), uuid.UUID)

    def test_email_is_unique(self) -> None:
        """User.email must be declared unique."""
        col = User.__table__.c.email
        assert col.unique

    def test_email_is_indexed(self) -> None:
        """User.email must be indexed (via index=True on the column or explicit index)."""
        # Either the column carries an index flag or a separate Index exists.
        col = User.__table__.c.email
        indexed_by_col = col.index
        indexed_by_table = any(
            "email" in [c.name for c in idx.columns]
            for idx in User.__table__.indexes
        )
        assert indexed_by_col or indexed_by_table

    def test_password_hash_column_exists(self) -> None:
        """User table must expose a 'password_hash' column."""
        assert "password_hash" in User.__table__.c

    def test_role_column_exists(self) -> None:
        """User table must expose a 'role' column."""
        assert "role" in User.__table__.c

    def test_check_constraint_defined(self) -> None:
        """users table must declare the ck_users_role check constraint."""
        constraint_names = {c.name for c in User.__table__.constraints}
        assert "ck_users_role" in constraint_names

    def test_repr_includes_email_and_role(self) -> None:
        """User __repr__ must include email and role."""
        user = User(email="bob@example.com", password_hash="hash", role="admin")
        user.id = uuid.uuid4()
        r = repr(user)
        assert "bob@example.com" in r
        assert "admin" in r

    def test_full_round_trip_hash_and_verify(self) -> None:
        """End-to-end: hash on User construction, verify with verify_password."""
        plain = "s3cur3P@ss"
        pw_hash = hash_password(plain, rounds=4)
        user = User(email="carol@example.com", password_hash=pw_hash, role="bookkeeper")

        assert user.email == "carol@example.com"
        assert user.role == "bookkeeper"
        # Verify the stored hash
        assert verify_password(plain, user.password_hash) is True
        assert verify_password("bad-guess", user.password_hash) is False
