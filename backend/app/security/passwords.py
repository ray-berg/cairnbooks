"""Password hashing utilities using bcrypt.

Usage::

    from app.security.passwords import hash_password, verify_password

    hashed = hash_password("my-secret")
    assert verify_password("my-secret", hashed)     # True
    assert not verify_password("wrong", hashed)     # False
"""

from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` if *plain* matches the bcrypt *hashed* value."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())
