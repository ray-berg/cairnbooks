# CairnBooks — Architecture Overview

> **Status:** Current | **Date:** 2026-06-07 | **Audience:** contributors, reviewers, operators

This document is the authoritative quick-reference for CairnBooks' system layers, data flow,
multi-tenancy enforcement, and architectural invariants.

For the full technology-stack rationale and decision records see
[ADR-0001-stack.md](./ADR-0001-stack.md).

---

## Table of Contents

1. [Layer Map](#1-layer-map)
2. [Layer Responsibilities](#2-layer-responsibilities)
3. [Dependency Rule](#3-dependency-rule)
4. [Request Data Flow](#4-request-data-flow)
5. [Background Job Data Flow](#5-background-job-data-flow)
6. [File Storage Flow](#6-file-storage-flow)
7. [Multi-Tenancy Enforcement](#7-multi-tenancy-enforcement)
8. [Architectural Invariants](#8-architectural-invariants)
9. [Technology at a Glance](#9-technology-at-a-glance)

---

## 1. Layer Map

```
╔══════════════════════════════════════════════════════════════════════╗
║                          External Clients                            ║
║       Browser (React 18 / Vite SPA)  │  Future mobile clients       ║
╚══════════════════════════════════════╤═══════════════════════════════╝
                                       │  HTTPS
╔══════════════════════════════════════▼═══════════════════════════════╗
║                     Reverse Proxy — Caddy 2                          ║
║           TLS termination · rate limiting · gzip                     ║
║     /api/*  →  FastAPI process     /*  →  static React bundle        ║
╚═════════════════════╤════════════════════════════════════════════════╝
                      │ /api/*
╔═════════════════════▼════════════════════════════════════════════════╗
║              PRESENTATION LAYER  (backend/app/api/)                  ║
║   FastAPI routers · Pydantic I/O schemas · Auth middleware           ║
║   OpenAPI 3.1 generation · WebSocket upgrade                         ║
╠══════════════════════════════════════════════════════════════════════╣
║              APPLICATION LAYER  (backend/app/services/)              ║
║   Use-case orchestration: PostJournalEntry, CreateInvoice,           ║
║   ReconcileBankFeed, GenerateReport …                                ║
║   Owns transaction boundaries · Enforces authorisation               ║
╠══════════════════════════════════════════════════════════════════════╣
║              DOMAIN LAYER  (backend/app/domain/)                     ║
║   Double-entry accounting engine · Balance invariants                ║
║   Tax rule engine · Currency conversion                              ║
║   Pure Python — zero I/O, zero framework imports                     ║
╠══════════════════════════════════════════════════════════════════════╣
║              INFRASTRUCTURE LAYER  (backend/app/infrastructure/)     ║
║   SQLAlchemy 2 repositories · S3 adapter (boto3)                     ║
║   Redis client · Email adapter · RQ / Arq task definitions           ║
╚══════════════════╤═══════════════════════════════╤════════════════════╝
                   │                               │
      ┌────────────┼───────────────────────────────┤
      │            │                               │
╔═════▼══════════╗ ╔══════════════╗  ╔═════════════▼══════════╗
║ PostgreSQL 16  ║ ║   Redis 7    ║  ║   Object Storage       ║
║ ACID storage   ║ ║ cache/broker ║  ║   MinIO (dev) / S3     ║
║ Row-Level Sec. ║ ╚══════╤═══════╝  ╚════════════════════════╝
╚════════════════╝        │
                  ╔═══════▼════════╗
                  ║  RQ / Arq      ║
                  ║  Workers       ║
                  ╚════════════════╝
```

---

## 2. Layer Responsibilities

| Layer | Module path | Owns | Must NOT |
|---|---|---|---|
| **Presentation** | `backend/app/api/` | HTTP routing, Pydantic request/response validation, auth middleware, OpenAPI generation, WebSocket upgrade | Contain business logic; issue SQL directly; import SQLAlchemy models |
| **Application** | `backend/app/services/` | Use-case orchestration, transaction boundaries, authorisation checks, background job dispatch | Contain HTTP concepts (status codes, headers); import SQLAlchemy models directly |
| **Domain** | `backend/app/domain/` | Accounting rules, double-entry invariants, balance calculations, tax engine, abstract repository protocols | Perform any I/O; import any framework (FastAPI, SQLAlchemy, boto3, Redis) |
| **Infrastructure** | `backend/app/infrastructure/` | Concrete database repositories, S3 adapter, Redis client, email adapter, RQ/Arq task definitions | Contain business logic; call Application services |
| **Frontend** | `frontend/src/` | UI rendering (SPA), API calls via TypeScript client, route-level code splitting | Touch the database directly; contain business logic |
| **Reverse Proxy** | Caddy config | TLS termination, HTTP→HTTPS redirect, gzip, upstream health checks, rate limiting | Inspect or mutate request bodies |
| **PostgreSQL** | — | Durable ACID storage, Row-Level Security (RLS) tenant isolation, audit-log immutability | — |
| **Redis** | — | RQ/Arq broker queues, response caching, rate-limit counters | — |
| **Object Storage** | — | Receipt/document blobs, invoice PDFs, export files, company assets | — |
| **RQ / Arq Workers** | `backend/app/infrastructure/jobs/` | Async job execution (reports, email, bank import, PDF generation) | Open HTTP connections to the API process |

---

## 3. Dependency Rule

Dependencies flow **inward only**:

```
Presentation  →  Application  →  Domain
Infrastructure  →  Domain   (implements interfaces defined in Domain)
```

The Domain layer defines abstract repository protocols using `typing.Protocol`
(e.g. `AccountRepository`, `JournalRepository`). The Infrastructure layer provides
concrete SQLAlchemy implementations. The Application layer depends on the protocols,
not the implementations — enabling unit tests to inject in-memory fakes.

**Corollary:** the Presentation layer may never import from `infrastructure/` directly;
it may only call Application service functions.

A CI lint rule (e.g. `import-linter`) flags any violation — for example
`api/` → `infrastructure/db/` or `domain/` → `api/`.

---

## 4. Request Data Flow

End-to-end path for an authenticated REST request (e.g. `POST /api/v1/journal-entries`):

```
Browser / Client
    │
    │  1. HTTPS request + Authorization: Bearer <access_token>
    ▼
Caddy (reverse proxy)
    │  2. TLS termination, rate-limit check, forward to API process
    ▼
Presentation Layer — FastAPI route handler
    │  3. Pydantic validates request body → 422 on schema error
    │  4. JWT middleware verifies access token → 401 on failure
    │  5. get_current_organisation() extracts organisation_id from token
    │     and stores it in contextvars.ContextVar (tenant context)
    ▼
Application Layer — service function
    │  6. Checks fiscal period status (must not be CLOSED)
    │  7. Opens a TenantSession (sets PostgreSQL session variable
    │     app.current_organisation_id before every SQL statement)
    │  8. Delegates to Domain layer for rule validation
    ▼
Domain Layer — pure Python
    │  9. Validates double-entry balance: sum(debits) == sum(credits)
    │  10. Asserts monetary precision (decimal.Decimal only; float rejected)
    │  11. Applies tax or currency-conversion rules if applicable
    │  Returns validated domain object (no I/O performed)
    ▼
Infrastructure Layer — repository
    │  12. SQLAlchemy flushes JournalEntry + JournalLines atomically
    │  13. SQLAlchemy event appends to AuditLog (append-only)
    │  14. session.commit() — PostgreSQL RLS enforces tenant isolation
    ▼
Presentation Layer — response serialisation
    │  15. Serialises to JSON: { "data": {...}, "meta": {...} }
    ▼
Browser / Client
```

**Error path:** any layer may raise a typed exception. FastAPI exception handlers convert
domain errors to RFC 9457 Problem Details (`application/problem+json`) before returning to
the client.

---

## 5. Background Job Data Flow

```
Application Layer (service function)
    │  1. Dispatches job with mandatory organisation_id argument
    ▼
Redis (RQ / Arq broker)
    │  2. Job message enqueued
    ▼
RQ / Arq Worker (TenantJob base)
    │  3. Restores tenant context: set_tenant_context(organisation_id)
    │  4. Executes job body (e.g. generate PDF, send email, import bank feed)
    │     ↳ Reads/writes via Infrastructure layer:
    │       TenantSession for PostgreSQL, boto3 for S3, SMTP adapter for email
    ▼
External services / data stores
    (PostgreSQL, MinIO/S3, SMTP relay)
```

Jobs that operate across all tenants (platform maintenance, health checks) run under a
separate `system` context with explicit superadmin privileges — never under a tenant context.

---

## 6. File Storage Flow

```
Upload (receipt, document):
    Client  →  POST /api/v1/files (multipart/form-data)
            →  Presentation layer validates MIME type + size limit
            →  Application layer calls the storage service
            →  Infrastructure: boto3.put_object →
               s3://<bucket>/orgs/<organisation_id>/<type>/<uuid>.<ext>
            →  Database stores a File record (S3 key, mime_type, size, linked entity)

Download (view receipt):
    Client  →  GET /api/v1/files/{id}/url
            →  Presentation layer authenticates + validates tenant ownership
            →  Infrastructure: boto3.generate_presigned_url (15-min TTL)
            →  Client fetches object directly from S3 endpoint (no app-server proxy)
```

The application server **never proxies file bytes**. Pre-signed URLs keep bandwidth and
latency off the API process and scale independently of the API tier.

---

## 7. Multi-Tenancy Enforcement

Tenant isolation is enforced at every layer; a failure at one layer is caught by the next:

| Layer | Mechanism |
|---|---|
| **JWT** | `organisation_id` claim embedded at login; verified on every request |
| **API middleware** | `get_current_organisation()` dependency sets `contextvars.ContextVar` |
| **ORM** | `TenantSession` sets PostgreSQL session variable `app.current_organisation_id` before every statement |
| **Database** | RLS policy `USING (organisation_id = current_setting('app.current_organisation_id')::uuid)` on every tenant table; the application role has no `BYPASSRLS` |
| **Background jobs** | `organisation_id` is a mandatory argument; `TenantJob` base class restores context before execution |
| **Object storage** | All object paths are prefixed `orgs/<organisation_id>/`; presigned URL generation validates the tenant match |

**Superadmin access:** cross-tenant operations (billing, platform maintenance) use a separate
PostgreSQL role with `BYPASSRLS`, a distinct JWT audience (`aud: cairnbooks-admin`), and an
IP allowlist. The application role used by normal API requests can never bypass RLS.

---

## 8. Architectural Invariants

These rules are non-negotiable. Violations are caught by tests, linters, or database
constraints before they reach production.

### 8.1 Accounting Invariants (Domain Layer)

| # | Invariant | Enforcement |
|---|---|---|
| I-1 | **Double-entry balance** — every `JournalEntry` must have `sum(debits) == sum(credits)` | Domain raises `JournalEntryImbalanceError` before persist |
| I-2 | **Immutable posted entries** — a `POSTED` entry's lines may never be mutated; corrections require a reversing entry | Domain raises on mutation attempt; column non-updatable via SQLAlchemy event |
| I-3 | **Monetary precision** — all amounts are `NUMERIC(20,6)` in PostgreSQL and `decimal.Decimal` in Python; `float` is prohibited | Pydantic validators + SQLAlchemy column type constraints |
| I-4 | **Multi-currency storage** — amounts always stored with ISO 4217 `currency_code`; base-currency conversion recorded at post time and never retroactively changed | Domain model enforces non-nullable `currency_code` |
| I-5 | **Audit trail** — all mutations to `Account`, `JournalEntry`, and `Invoice` append to an append-only `audit_log` table via SQLAlchemy events | Database role has no `UPDATE`/`DELETE` on `audit_log` |
| I-6 | **Fiscal period lock** — transactions cannot be posted to a `FiscalPeriod` with `status = CLOSED` | Application layer checks period status before Domain delegation |

### 8.2 Multi-Tenancy Invariants

| # | Invariant | Enforcement |
|---|---|---|
| I-7 | Every query, mutation, background job, and stored object is scoped to a single `organisation_id` | RLS + TenantSession + TenantJob (see §7) |
| I-8 | Cross-tenant access by privileged code is prohibited except in a dedicated superadmin context | Separate PostgreSQL role (`BYPASSRLS`), separate JWT audience, IP allowlist |

### 8.3 API Invariants

| # | Invariant | Enforcement |
|---|---|---|
| I-9 | **API-first** — every feature is an HTTP endpoint; no server-rendered HTML from the backend; no frontend has direct DB access | Architecture policy; CI checks OpenAPI spec generation |
| I-10 | All API responses use the `{ "data": ..., "meta": { "pagination"?: ... } }` envelope | Shared response model in Presentation layer |
| I-11 | All errors follow RFC 9457 Problem Details (`application/problem+json`) | FastAPI exception handlers |

### 8.4 Infrastructure Invariants

| # | Invariant | Enforcement |
|---|---|---|
| I-12 | The API server never proxies file bytes; pre-signed URLs only | Architecture policy; no static-file serving in FastAPI routes |
| I-13 | All configuration is via environment variables (12-factor); no secrets committed to version control | `.env.example` documents required vars; `.gitignore` excludes `.env` and `*.env` |
| I-14 | Background jobs are idempotent and carry a deduplicated task ID | Task design guideline; enforced in code review |

---

## 9. Technology at a Glance

| Concern | Technology | Version |
|---|---|---|
| Backend language | Python | 3.12+ |
| Backend framework | FastAPI + Uvicorn | 0.115+ |
| ORM / migrations | SQLAlchemy 2 + Alembic | 2.x / 1.x |
| Frontend framework | React + Vite (SPA) | 18+ / 5+ |
| Frontend language | TypeScript | 5.x |
| UI styling | Tailwind CSS | 3.x |
| Relational database | PostgreSQL | 16+ |
| Background jobs | RQ (Redis Queue) or Arq | latest |
| Cache / job broker | Redis | 7.x |
| Object storage | MinIO (dev) / S3-compatible (prod) | — |
| Auth | JWT — access 15 min + refresh 7 days | via `python-jose` |
| Reverse proxy | Caddy | 2.x |
| Container runtime | Docker + Docker Compose | — |

For the full rationale behind each technology choice see
[ADR-0001-stack.md § 3 Stack Rationale](./ADR-0001-stack.md#3-stack-rationale).
