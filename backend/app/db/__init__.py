"""Infrastructure / database layer.

Responsibilities
----------------
- SQLAlchemy 2.0 async engine and session factory.
- Repository implementations (queries and persistence).
- Redis client.
- S3 / object-storage client.
- Email and notification adapters.
- Celery task definitions.

Must NOT
--------
- Contain business rules or domain logic.
- Leak ORM model internals into the service or API layers
  (return domain objects, not ORM rows, where possible).
"""
