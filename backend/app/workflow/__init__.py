"""Workflow / service layer — use-case orchestration.

Each module in this package owns a single aggregate's lifecycle operations
(create, read, update, list, deactivate/delete).  Modules:

- :mod:`app.workflow.attachments` — Attachment upload/download service.
- :mod:`app.workflow.customers` — Customer CRUD service.

Design rules
------------
- All operations are tenant-scoped; every function accepts ``tenant_id`` and
  filters all queries accordingly.
- Functions accept an ``AsyncSession`` dependency and call ``flush()`` rather
  than ``commit()`` so that the caller (e.g. an API route) controls the
  transaction boundary.
- No HTTP or FastAPI imports here — this layer must stay framework-agnostic.
"""
