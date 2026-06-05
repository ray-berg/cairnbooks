"""Presentation layer — HTTP routing and request/response schemas.

Responsibilities
----------------
- Route handlers (FastAPI routers)
- Pydantic I/O schemas (request bodies, response models)
- Auth middleware / dependency injection
- Rate limiting hooks

Must NOT
--------
- Contain business logic
- Access the database directly (always go through a service)
"""
