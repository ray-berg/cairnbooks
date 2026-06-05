"""Application / services layer — use-case orchestration.

Responsibilities
----------------
- Orchestrate domain objects and infrastructure adapters to fulfil a use case
  (e.g. PostJournalEntry, CreateInvoice, ReconcileBankFeed).
- Own transaction boundaries (begin / commit / rollback).
- Emit domain events.

Must NOT
--------
- Know about HTTP, request/response details, or status codes.
- Contain SQL syntax or direct storage-URL construction.
- Implement core accounting rules (those live in :mod:`app.domain`).
"""
