"""Password hashing and verification using bcrypt.

Usage
-----
Hash a password on registration::

    from cairnbooks.security.passwords import hash_password, verify_password

    pw_hash = hash_password("super-secret")

Verify on login::

    is_valid = verify_password("super-secret", pw_hash)  # True
    is_valid = verify_password("wrong-pass", pw_hash)    # False

Security notes
--------------
- ``bcrypt.gensalt()`` uses a cost factor of 12 by default, which is
  sufficient for current hardware.  Increase ``rounds`` if the threat model
  demands slower hashing.
- Passwords and hashes are handled as ``bytes`` internally; the public API
  accepts and returns ``str`` for convenience.
"""

from __future__ import annotations

import bcrypt


def hash_password(plain: str, *, rounds: int = 12) -> str:
    """Hash *plain* with bcrypt and return the hash as a UTF-8 string.

    Args:
        plain:  The plain-text password supplied by the user.
        rounds: bcrypt work-factor (cost).  Higher values are slower but
                more resistant to brute-force attacks.  Default is 12.

    Returns:
        A bcrypt hash string suitable for storage in the ``password_hash``
        column (e.g. ``"$2b$12$..."``).
    """
    salt = bcrypt.gensalt(rounds=rounds)
    hashed: bytes = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify *plain* against a bcrypt *hashed* value.

    Args:
        plain:  The plain-text password to check.
        hashed: The bcrypt hash previously produced by :func:`hash_password`.

    Returns:
        ``True`` if *plain* matches the hash, ``False`` otherwise.
    """
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
