# CairnBooks — Architecture Overview

> Status: **Current** | Date: 2026-06-05 | Audience: contributors, reviewers, operators

This document is the authoritative quick-reference for CairnBooks' system layers, request/data flow, and architectural invariants. For full rationale and ADRs see [`docs/architecture.md`](./architecture.md).

---

## Table of Contents

1. [Layer Map](#1-layer-map)
2. [Layer Responsibilities](#2-layer-responsibilities)
3. [Request Data Flow](#3-request-data-flow)
4. [Background Job Data Flow](#4-background-job-data-flow)
5. [File Storage Flow](#5-file-storage-flow)
6. [Multi-Tenancy Enforcement](#6-multi-tenancy-enforcement)
7. [Architectural Invariants](#7-architectural-invariants)
8. [Technology at a Glance](#8-technology-at-a-glance)

---

## 1. Layer Map

```
╔══════════════════════════════════════════════════════════════════╗
║                         External Clients                         ║
║          Browser (Next.js SSR/SPA)  │  Mobile (future)          ║
╚══════════════════════════════════════╤═══════════════════════════╝
                                       │  HTTPS / WSS
╔══════════════════════════════════════▼═══════════════════════════╗
║                     Reverse Proxy — Caddy 2                      ║
║             TLS termination · rate limiting · gzip               ║
╚═════════════════╤══════════════════════════╤═════════════════════╝
                  │ /api/*                   │ /*
╔═════════════════▼══════════╗   ╔═══════════▼═════════════════════╗
║  API Process (FastAPI)     ║   ║  Frontend Process (Next.js 15)  ║
║  Uvicorn · Gunicorn        ║   ║  TypeScript · Tailwind · shadcn ║
╠════════════════════════════╣   ╚═════════════════════════════════╝
║  Presentation Layer        ║  ← HTTP routing, Pydantic I/O
║                            ║    schemas, auth middleware,
║                            ║    rate limiting, OpenAPI
╠════════════════════════════╣
║  Application Layer         ║  ← Use-case services (e.g.
║  (Services)                ║    PostJournalEntry, CreateInvoice,
║                            ║    ReconcileBankFeed). Owns
║                            ║    transaction boundaries.
╠════════════════════════════╣
║  Domain Layer              ║  ← Accounting rules, double-entry
║                            ║    invariants, tax engine, currency
║                            ║    conversion. Zero I/O, zero
║                            ║    framework imports.
╠════════════════════════════╣
║  Infrastructure Layer      ║  ← SQLAlchemy 2.0 repositories,
║                            ║    S3 client (boto3), Redis client,
║                            ║    email adapter, Celery task defs
╚═════════════╤══════════════╝
              │
   ┌──────────┼──────────────────────────────┐
   │          │                              │
╔══▼══════════╗  ╔══════════════╗  ╔══════════▼════════════╗
║ PostgreSQL  ║  ║   Redis 7    ║  ║   Object Storage      ║
║    16       ║  ║ cache/broker ║  ║  S3-compatible        ║
║ primary +   ║  ╚══════╤═══════╝  ║  (Wasabi/S3/MinIO)    ║
║ read replica║         │          ╚═══════════════════════╝
╚═════════════╝  ╔══════▼═══════╗
                 ║ Celery Workers║
                 ║ (background   ║
                 ║  jobs)        ║
                 ╚══════════════╝
```

---

## 2. Layer Responsibilities

| Layer | Owns | Must NOT |
|---|---|---|
| **Frontend** (Next.js) | UI rendering (SSR + SSG), API calls via generated TypeScript client, route-level code splitting | Touch the database directly; contain business logic |
| **Reverse Proxy** (Caddy) | TLS termination, HTTP→HTTPS redirect, gzip, upstream health checks, rate limiting | Inspect or mutate request bodies |
| **Presentation** (FastAPI routes) | HTTP routing, request/response validation (Pydantic), authentication middleware, OpenAPI generation, WebSocket upgrade | Contain business logic; issue SQL directly |
| **Application / Services** | Use-case orchestration, transaction boundaries, domain event emission, Celery task dispatch | Know about HTTP details, SQL syntax, or storage URLs |
| **Domain** | Core accounting entities, double-entry rules, tax engine, monetary arithmetic, currency conversion | Import any framework or I/O library |
| **Infrastructure** | SQLAlchemy sessions & repositories, S3/boto3 client, Redis client, email adapter, Celery task definitions | Contain business rules or validation logic |
| **PostgreSQL** | Durable ACID storage, Row-Level Security (RLS) tenant isolation, audit log immutability | — |
| **Redis** | Celery broker queues, response caching, session storage | — |
| **Object Storage** | Receipt/document blobs, invoice PDFs, export files, company assets | — |
| **Celery Workers** | Async job execution (reports, email, bank import, invoice generation) | Open HTTP connections to the API process |

---

## 3. Request Data Flow

Below is the end-to-end path for an authenticated REST request (e.g. `POST /api/v1/journal-entries`):

```
Browser / Client
    │
    │  1. HTTPS request + Authorization: Bearer <access_token>
    ▼
Caddy (reverse proxy)
    │  2. TLS termination, rate-limit check, forward to API pool
    ▼
Presentation Layer (FastAPI route handler)
    │  3. Pydantic validates request body → raises 422 on schema error
    │  4. JWT middleware verifies access token → raises 401 on failure
    │  5. get_current_organization() extracts organization_id from token
    │     and writes it to a contextvars.ContextVar (sets tenant context)
    ▼
Application Layer (service function)
    │  6. Checks fiscal period status (not CLOSED)
    │  7. Opens a TenantSession (sets PostgreSQL session variable
    │     app.current_organization_id before every statement)
    │  8. Delegates to Domain layer for rule validation
    ▼
Domain Layer
    │  9. Validates double-entry balance (sum debits == sum credits)
    │  10. Asserts monetary precision (decimal.Decimal only)
    │  11. Applies any tax or currency-conversion rules
    │  Returns validated domain object (no I/O)
    ▼
Infrastructure Layer (repository)
    │  12. SQLAlchemy flushes JournalEntry + JournalLines atomically
    │  13. SQLAlchemy event appends to AuditLog (append-only)
    │  14. session.commit() — PostgreSQL RLS enforces tenant isolation
    ▼
Presentation Layer (response)
    │  15. Serialises to JSON response envelope { data: ..., meta: ... }
    ▼
Browser / Client
```

**Error path**: Any layer may raise a typed exception. FastAPI exception handlers convert domain errors to RFC 9457 Problem Details (`application/problem+json`) before they reach the client.

---

## 4. Background Job Data Flow

```
Application Layer (service)
    │  1. Dispatches Celery task with mandatory organization_id kwarg
    ▼
Redis (broker)
    │  2. Task message enqueued
    ▼
Celery Worker (TenantTask base class)
    │  3. Restores tenant context: set_tenant_context(organization_id)
    │  4. Executes task body (e.g. generate PDF, send email, import bank feed)
    │     ↳ Reads/writes via Infrastructure layer (TenantSession for DB,
    │       boto3 for S3, SMTP adapter for email)
    ▼
External services / Data stores
    (PostgreSQL, S3, SMTP relay)
```

Tasks that operate across all tenants (platform health checks, system maintenance) run under a separate `system` context with explicit superadmin privileges — never under a tenant context.

---

## 5. File Storage Flow

```
Upload (receipt, document):
    Client → POST /api/v1/files (multipart)
           → Presentation layer validates MIME type + size
           → Application layer calls S3 client
           → Infrastructure layer: boto3.put_object to
             s3://<bucket>/orgs/<organization_id>/<type>/<uuid>.<ext>
           → Database stores File record (S3 key, mime_type, size, linked entity)

Download (view receipt):
    Client → GET /api/v1/files/{id}/url
           → Presentation layer authenticates request + validates tenant ownership
           → Infrastructure layer: boto3.generate_presigned_url (15-min TTL)
           → Client fetches object directly from S3 endpoint (no app-server proxy)
```

The application server **never proxies file bytes**. Pre-signed URLs keep bandwidth off the API process.

---

## 6. Multi-Tenancy Enforcement

Tenant isolation is enforced at **every layer**; a failure at one layer is caught by the next:

| Layer | Mechanism |
|---|---|
| **JWT** | `organization_id` claim embedded at login; verified on every request |
| **API middleware** | `get_current_organization()` dependency sets `contextvars.ContextVar` |
| **ORM** | `TenantSession` sets PostgreSQL session variable `app.current_organization_id` before every statement |
| **Database** | RLS policy `USING (organization_id = current_setting('app.current_organization_id')::uuid)` on every tenant table; app role has no `BYPASSRLS` |
| **Celery tasks** | `organization_id` is a mandatory kwarg; `TenantTask` base class restores context before execution |
| **Object storage** | All paths prefixed `orgs/<organization_id>/`; presigned URL generation validates tenant match |

---

## 7. Architectural Invariants

These rules are non-negotiable. Violations are caught by tests, linters, or database constraints before they reach production.

### 7.1 Accounting Invariants (Domain Layer)

| # | Invariant | Enforcement |
|---|---|---|
| I-1 | **Double-entry balance**: every `JournalEntry` must have `sum(debits) == sum(credits)` | Domain raises `JournalEntryImbalanceError` before persist |
| I-2 | **Immutable posted entries**: a `POSTED` journal entry's lines may never be mutated; corrections require a reversing entry | Domain raises on mutation attempt; DB column marked non-updatable via SQLAlchemy |
| I-3 | **Monetary precision**: all amounts are `NUMERIC(20, 6)` in PostgreSQL and `decimal.Decimal` in Python; `float` is prohibited | Pydantic validators + SQLAlchemy column type constraints |
| I-4 | **Multi-currency storage**: amounts always stored with their ISO 4217 `currency_code`; base-currency conversion recorded at post time and never retroactively changed | Domain model enforces currency_code as non-nullable |
| I-5 | **Audit trail**: all mutations to `Account`, `JournalEntry`, and `Invoice` append to an append-only `AuditLog` table via SQLAlchemy events | Database role has no `UPDATE`/`DELETE` on `audit_log` |
| I-6 | **Fiscal period lock**: transactions cannot be posted to a `FiscalPeriod` with `status = CLOSED` | Application layer checks period status before domain delegation |

### 7.2 Multi-Tenancy Invariants

| # | Invariant | Enforcement |
|---|---|---|
| I-7 | Every query, mutation, background job, and stored object is scoped to a single `organization_id` | RLS + TenantSession + TenantTask (see §6) |
| I-8 | Cross-tenant access — even by privileged application code — is prohibited except in a dedicated superadmin context | Superadmin uses a separate PostgreSQL role (`BYPASSRLS`), separate JWT audience (`aud: cairnbooks-admin`), and IP allowlist |

### 7.3 API Invariants

| # | Invariant | Enforcement |
|---|---|---|
| I-9 | **API-first**: every feature is expressed as an HTTP endpoint; no server-rendered HTML from the backend; no frontend has privileged DB access | Architecture policy; CI checks OpenAPI spec generation |
| I-10 | All API responses use the `{ data: ..., meta: { pagination? } }` envelope | Shared response model in Presentation layer |
| I-11 | All errors follow RFC 9457 Problem Details (`application/problem+json`) | FastAPI exception handlers |

### 7.4 Infrastructure Invariants

| # | Invariant | Enforcement |
|---|---|---|
| I-12 | Application server never proxies file bytes; pre-signed URLs only | Architecture policy; no static file serving in FastAPI routes |
| I-13 | All configuration is via environment variables (12-factor); no secrets committed | `.env.example` documents required vars; `.gitignore` excludes `.env` |
| I-14 | Celery tasks are idempotent and carry a deduplicated task-id | Task design guideline; enforced in code review |

---

## 8. Technology at a Glance

| Concern | Technology | Version |
|---|---|---|
| Backend language | Python | 3.12+ |
| Backend framework | FastAPI + Uvicorn/Gunicorn | 0.115+ |
| Frontend framework | Next.js (App Router) | 15+ |
| Frontend language | TypeScript | 5.x |
| UI components | Tailwind CSS + shadcn/ui | latest |
| Relational database | PostgreSQL | 16+ |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | 2.x |
| Background jobs | Celery + Redis (broker) | 5.x / 7.x |
| Caching / pub-sub | Redis | 7.x |
| Object storage | S3-compatible (Wasabi / AWS S3 / MinIO) | — |
| Auth | JWT (access 15 min + refresh 7 days) via `python-jose` | — |
| Reverse proxy | Caddy | 2.x |
| Container runtime | Docker + Docker Compose | — |

For full rationale behind each choice see [`docs/architecture.md §3`](./architecture.md#3-rationale).
