"""Domain layer — core accounting rules and entity models.

Responsibilities
----------------
- Accounting invariants (double-entry balance, immutable posted entries,
  monetary precision, multi-currency, audit trail, fiscal-period locks).
- Pure Python entity and value-object classes.
- Domain events.

Must NOT
--------
- Import any framework or I/O library (FastAPI, SQLAlchemy, Redis, etc.).
- Perform network or disk I/O.

This layer is unit-testable in complete isolation from infrastructure.
"""
