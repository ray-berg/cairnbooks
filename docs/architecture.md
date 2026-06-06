# CairnBooks — Architecture Proposal

> **Status: PENDING HUMAN APPROVAL**
> This document requires explicit sign-off before implementation begins.
> See [Approval Gate](#approval-gate) at the bottom.

---

## Table of Contents

1. [Overview](#overview)
2. [Stack Selection](#stack-selection)
3. [Layered Architecture](#layered-architecture)
4. [Posting Engine Invariants](#posting-engine-invariants)
5. [Audit Log](#audit-log)
6. [Multi-Tenant Data Model](#multi-tenant-data-model)
7. [Approval Gate](#approval-gate)

---

## Overview

CairnBooks is a multi-tenant, double-entry bookkeeping SaaS. The architecture must satisfy several non-negotiable properties from day one:

- **Correctness over throughput** — every journal entry must balance; a wrong number is worse than a slow one.
- **Immutability of posted data** — once a period is closed, its records cannot be silently altered.
- **Full auditability** — every write carries who, what, when, and why.
- **Strict tenant isolation** — one tenant must never see another tenant's data, even in the event of a query bug.
- **Evolvability** — the schema and API must accommodate new ledger types, currencies, and integrations without rewriting core logic.

---

## Stack Selection

### Backend — Python 3.12 + FastAPI

| Consideration | Rationale |
|---|---|
| **Language** | Python's type-hint ecosystem (Pydantic, mypy) provides compile-time-like guarantees for data shapes without sacrificing developer velocity. The financial/accounting ecosystem (pandas, numpy, babel for currency) is unmatched. |
| **Framework** | FastAPI gives us async-first request handling, automatic OpenAPI documentation, and native Pydantic model validation at the boundary — every request in and out is schema-checked with no boilerplate. |
| **Alternatives considered** | Go (excellent performance, weaker financial libs); Node/NestJS (large ecosystem, but runtime type erasure is risky for financial amounts); Rails (great for CRUD, but Python's numerical tooling wins). |

### Frontend — Next.js 14 (React, TypeScript)

| Consideration | Rationale |
|---|---|
| **Framework** | Next.js App Router gives us server components (fast initial render, no credential leakage to the client), static generation for marketing pages, and streaming for report pages. |
| **Type Safety** | TypeScript end-to-end, with generated API clients (openapi-typescript) so API schema changes surface as compile errors in the frontend. |
| **Alternatives considered** | SvelteKit (smaller community, fewer accounting UI component libraries); plain Vite/React (no SSR without extra work). |

### Database — PostgreSQL 16

PostgreSQL is the only reasonable choice for financial software:

- **ACID transactions** with serializable isolation level available when needed (ledger posting).
- **Row-Level Security (RLS)** — native enforcement of tenant isolation at the database layer, not just the application layer.
- **`numeric` type** — exact decimal arithmetic; `float`/`double` are forbidden for monetary values.
- **`generated columns`** and `CHECK` constraints allow encoding accounting invariants at the schema level.
- **Full-text search**, JSONB, and arrays reduce the need for auxiliary stores.

### ORM — SQLAlchemy 2.x + Alembic

| Consideration | Rationale |
|---|---|
| **SQLAlchemy 2.x** | Async-native ORM with explicit session management. The 2.x unified style eliminates the legacy "legacy" query API entirely. SQLModel wraps it for Pydantic integration. |
| **Alembic** | Migration engine with auto-generation from model diffs; supports multi-head branching for parallel development. |
| **Raw SQL where needed** | Complex ledger queries (trial balance, balance sheet) are expressed as named raw SQL files, not ORM chains — clarity and debuggability matter more than abstraction for financial reports. |

### Job Queue — Celery 5 + Redis 7

| Consideration | Rationale |
|---|---|
| **Celery** | Mature, battle-tested task queue with Django/SQLAlchemy integration. Supports task routing (ledger posting on a dedicated queue), rate limiting, and retry policies with exponential back-off. |
| **Redis** | Broker and result backend. Also used for rate limiting, idempotency-key caching, and short-lived session tokens. |
| **Use cases** | Async PDF/CSV report generation, bank-feed ingestion, recurring-transaction scheduling, email/notification dispatch, period-close side effects. |
| **Alternatives considered** | Temporal (superior for long-running workflows, but operationally complex for v1); BullMQ (Node-only); RQ (simpler but less feature-rich). |

### Object Storage — AWS S3 (MinIO for local/self-hosted)

| Consideration | Rationale |
|---|---|
| **S3** | Industry standard; pre-signed URLs mean the app server never proxies large file bytes. |
| **MinIO** | S3-compatible; used in Docker Compose for local development so no AWS account is needed to run the stack. |
| **Stored objects** | Exported reports (PDF, XLSX, CSV), uploaded receipts/attachments, bank statement files, tenant data exports. |
| **Security** | Server-side encryption (SSE-S3 or SSE-KMS); all bucket policies deny public access; objects addressed by UUID, never by tenant name. |

### Supporting Infrastructure

| Component | Choice | Notes |
|---|---|---|
| **Auth** | Auth0 / Supabase Auth (OIDC) | JWT + refresh tokens; RBAC claims embedded in token |
| **Email** | Resend (SMTP fallback) | Transactional email with webhooks |
| **Observability** | OpenTelemetry → Grafana stack | Traces, metrics, logs unified |
| **CI/CD** | GitHub Actions | Lint → test → build → deploy |
| **Container runtime** | Docker + docker-compose (dev), ECS/Fargate or Fly.io (prod) | No Kubernetes for v1 |
| **Secrets** | AWS Secrets Manager / Doppler | Never in env files committed to git |

---

## Layered Architecture

The application enforces a strict dependency rule: **outer layers depend on inner layers; inner layers never import from outer layers.**

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                 │
│          Browser (Next.js)   ·   CLI   ·   Webhooks             │
└───────────────────────────┬─────────────────────────────────────┘
                            │  HTTPS / JSON
┌───────────────────────────▼─────────────────────────────────────┐
│                      API LAYER  (FastAPI)                        │
│   Routes · Request validation (Pydantic) · Auth middleware       │
│   Rate limiting · Idempotency key enforcement                    │
│   OpenAPI schema auto-generated                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │  Python function calls
┌───────────────────────────▼─────────────────────────────────────┐
│                    SERVICE LAYER                                  │
│   Use-case orchestration (one class per use case)                │
│   Transaction boundaries owned here                              │
│   Emits domain events → job queue                                │
│   No HTTP concepts; no ORM models exposed outward                │
└──────────┬────────────────┬──────────────────────────────────────┘
           │                │
┌──────────▼──────┐  ┌──────▼──────────────────────────────────── ┐
│  DOMAIN LAYER   │  │           POSTING ENGINE                    │
│                 │  │  Pure Python; zero I/O                      │
│  Entities:      │  │  Validates & builds JournalEntry objects    │
│  · Account      │  │  Enforces all invariants (see §4)           │
│  · JournalEntry │  │  Returns Result[PostedEntry, PostingError]  │
│  · LedgerLine   │  │  Never touches DB directly                  │
│  · Period       │  │                                             │
│  · Tenant       │  │  Input  → validate → build → return         │
│  Value objects: │  │  (Service layer persists the result)        │
│  · Money        │  └─────────────────────────────────────────────┘
│  · AccountCode  │
│  · FiscalPeriod │
└──────────┬──────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│                  REPOSITORY LAYER  (SQLAlchemy)                  │
│   One repository per aggregate root                              │
│   Returns domain objects, not ORM row objects                    │
│   Enforces tenant_id scoping on every query                      │
│   Raw SQL for complex reads (reports); ORM for writes            │
└──────────┬──────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│                   PERSISTENCE  (PostgreSQL)                      │
│   Row-Level Security policies enforce tenant_id                  │
│   CHECK constraints enforce accounting invariants                │
│   Append-only audit_log table (no UPDATE/DELETE)                 │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Contracts

| Layer | May import from | May NOT import from |
|---|---|---|
| Domain | nothing (pure Python) | Repository, Service, API |
| Posting Engine | Domain only | Repository, Service, API |
| Repository | Domain | Service, API |
| Service | Domain, Posting Engine, Repository | API |
| API | Service | Domain internals, Repository |

**Cross-cutting concerns** (logging, tracing, auth context) are passed as explicit parameters or via `contextvars`, never via global state.

---

## Posting Engine Invariants

The posting engine is the authoritative gatekeeper for all ledger writes. It is **pure** (no I/O, deterministic) so it can be unit-tested exhaustively without a database.

### I1 — Double-Entry Balance

Every `JournalEntry` accepted by the engine must satisfy:

```
Σ debit_amounts == Σ credit_amounts
```

in the functional currency of the entry. The engine rejects any entry where this sum differs by even one cent (or the smallest denomination of the operating currency). There are no exceptions.

### I2 — Open Period

A journal entry may only be posted into a fiscal period with status `OPEN`. The engine checks:

```
period.status == PeriodStatus.OPEN
AND entry.transaction_date IN period.date_range
```

Posting into a `CLOSED` or `LOCKED` period raises `PeriodClosedError`. Re-opening a closed period requires an explicit admin action that is itself audit-logged.

### I3 — Valid Account Codes

Every ledger line must reference an account that:
- Exists in the tenant's chart of accounts.
- Is in `ACTIVE` status (not archived or suspended).
- Accepts the entry type (e.g., a revenue account cannot receive an asset debit without explicit override).

### I4 — Currency Consistency

All ledger lines within a single journal entry must use the same transaction currency (multi-currency entries are split into separate FX-rate entries by the service layer before reaching the posting engine). The engine does not perform currency conversion — it enforces consistency.

### I5 — Idempotency

Every posting request carries an `idempotency_key` (UUID v4, generated by the caller). The engine (via the service layer) checks an `idempotency_cache` (Redis, TTL 24h) before calling the engine. A duplicate key with identical payload returns the already-posted entry. A duplicate key with a different payload raises `IdempotencyConflictError`.

### I6 — Immutability of Posted Entries

The engine produces `PostedEntry` objects; these are written to the database as `INSERT`-only rows. There are **no UPDATE or DELETE paths** for posted ledger lines. Corrections are made through reversing entries (a new balancing `JournalEntry` with a `reversal_of` foreign key).

### I7 — Tenant Isolation

Every `PostedEntry` carries a `tenant_id` stamped at entry creation. The posting engine asserts `entry.tenant_id == current_tenant_context.tenant_id` before proceeding. A mismatch raises `TenantMismatchError` and triggers a security alert.

### I8 — Numeric Precision

All monetary amounts are `decimal.Decimal` in Python and `NUMERIC(20, 6)` in PostgreSQL. Floating-point types are banned in the financial data path. The posting engine enforces this at the type level via a `Money` value object that wraps `Decimal`.

### I9 — Audit Trail Required

The engine accepts an `actor` (user ID or system process ID) and a `reason` string. Both are mandatory. A posting attempt without an actor or reason is rejected before any validation occurs.

---

## Audit Log

### Design Principles

- **Append-only forever.** No row in `audit_log` is ever UPDATE'd or DELETE'd. Even admins cannot delete audit rows through the application.
- **Out-of-band.** The audit log is written in the same database transaction as the primary write but to a separate table. If the primary write rolls back, the audit row rolls back with it — the log reflects only committed state.
- **Structured and queryable.** Each row is fully self-describing (JSON payload) and indexed for common queries (by tenant, by actor, by resource, by time).

### Schema

```sql
CREATE TABLE audit_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID        NOT NULL REFERENCES tenants(id),
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_type    TEXT        NOT NULL,  -- 'user' | 'system' | 'integration'
    actor_id      UUID        NOT NULL,
    actor_email   TEXT,                  -- denormalised snapshot at time of action
    action        TEXT        NOT NULL,  -- e.g. 'journal_entry.posted'
    resource_type TEXT        NOT NULL,  -- e.g. 'JournalEntry'
    resource_id   UUID        NOT NULL,
    before_state  JSONB,                 -- null for creates
    after_state   JSONB,                 -- null for deletes
    metadata      JSONB NOT NULL DEFAULT '{}',
                                         -- ip_address, user_agent, reason, etc.
    CONSTRAINT audit_log_no_future CHECK (occurred_at <= now() + interval '5 seconds')
);

-- Revoke UPDATE and DELETE from the application role
REVOKE UPDATE, DELETE ON audit_log FROM cairnbooks_app;

-- Indexes
CREATE INDEX ON audit_log (tenant_id, occurred_at DESC);
CREATE INDEX ON audit_log (tenant_id, resource_type, resource_id);
CREATE INDEX ON audit_log (tenant_id, actor_id, occurred_at DESC);
```

### What Is Logged

| Event | action value | Notes |
|---|---|---|
| Journal entry posted | `journal_entry.posted` | Full entry in `after_state` |
| Journal entry reversed | `journal_entry.reversed` | Links to original via `metadata.reversal_of` |
| Period opened | `period.opened` | |
| Period closed | `period.closed` | Includes who approved |
| Period re-opened | `period.reopened` | Requires admin; always logged |
| Account created / archived | `account.created` / `account.archived` | |
| User invited / removed | `user.invited` / `user.removed` | |
| Role changed | `user.role_changed` | `before_state` and `after_state` include role |
| Tenant settings changed | `tenant.settings_updated` | Diff in before/after |
| Export downloaded | `export.downloaded` | Who downloaded what |
| Login / logout | `session.created` / `session.ended` | |
| Failed posting attempt | `journal_entry.post_failed` | `metadata.reason` explains invariant violated |

### Retention and Archival

- Hot tier: PostgreSQL, rolling 13 months.
- Cold tier: Monthly export to S3 as compressed JSONL; retained for 7 years (accounting compliance).
- Archival is triggered by a Celery periodic task; the S3 object key encodes `tenant_id/year/month`.

---

## Multi-Tenant Data Model

### Tenancy Strategy — Row-Level Tenancy with PostgreSQL RLS

CairnBooks uses **shared schema, row-level tenancy** enforced at the database layer via PostgreSQL Row-Level Security. This gives us:

- Single database instance (low ops overhead at v1 scale).
- True database-level enforcement — a misconfigured query cannot cross tenant boundaries.
- Easy upgrade path to separate schemas or databases per tenant when a customer requires it.

### Core Tenant Tables

```sql
-- Master tenant registry
CREATE TABLE tenants (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug              TEXT UNIQUE NOT NULL,  -- URL-safe identifier
    display_name      TEXT NOT NULL,
    plan              TEXT NOT NULL DEFAULT 'starter',
    currency          CHAR(3) NOT NULL DEFAULT 'USD',  -- ISO 4217
    fiscal_year_start SMALLINT NOT NULL DEFAULT 1,     -- month 1-12
    timezone          TEXT NOT NULL DEFAULT 'UTC',
    status            TEXT NOT NULL DEFAULT 'active',  -- active | suspended | cancelled
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    settings          JSONB NOT NULL DEFAULT '{}'
);

-- Every tenant-scoped table follows this pattern:
CREATE TABLE journal_entries (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id),
    -- ... domain columns ...
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS on every tenant-scoped table
ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON journal_entries
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Application sets the tenant context at connection time:
-- SET LOCAL app.current_tenant_id = '<tenant-uuid>';
```

### Setting Tenant Context

The repository layer sets the tenant context at the start of every database transaction:

```python
async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    await session.execute(
        text("SET LOCAL app.current_tenant_id = :tid"),
        {"tid": str(tenant_id)},
    )
```

FastAPI middleware extracts the tenant from the JWT `tenant_id` claim and stores it in a `contextvars.ContextVar`. The repository base class reads it automatically — no passing tenant IDs through every function call.

### Tenant-Scoped Tables (summary)

```
tenants                     ← root; no tenant_id column
  ├── users                 ← tenant_id (a user belongs to one tenant in v1)
  ├── user_invitations
  ├── roles / permissions
  ├── chart_of_accounts
  │    └── accounts
  ├── fiscal_periods
  ├── journal_entries
  │    └── journal_lines    ← the individual debit/credit lines
  ├── attachments           ← S3 object references
  ├── bank_feeds
  ├── audit_log             ← append-only
  └── exports               ← report export metadata
```

### User ↔ Tenant Relationship

In v1, users belong to exactly one tenant (simple). In v2, a user may manage multiple tenants (accounting firms). The join table is reserved but not enforced in v1:

```sql
-- v1: one-to-one shortcut
ALTER TABLE users ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);

-- v2 migration path (prepared but not activated in v1):
-- CREATE TABLE user_tenant_memberships (
--     user_id   UUID NOT NULL REFERENCES users(id),
--     tenant_id UUID NOT NULL REFERENCES tenants(id),
--     role      TEXT NOT NULL,
--     PRIMARY KEY (user_id, tenant_id)
-- );
```

### RBAC Model

Roles are stored per-tenant and checked by the service layer before any mutation:

| Role | Description |
|---|---|
| `owner` | Full control; can delete the tenant account |
| `admin` | Manage users, settings, close periods |
| `accountant` | Post and reverse journal entries; manage chart of accounts |
| `viewer` | Read-only access to all financial data |
| `auditor` | Read-only + full audit log access |

Role checks are enforced in the service layer (not the route layer) so they apply regardless of how the service is called (HTTP, CLI, background job).

### Tenant Provisioning Flow

```
1. Owner signs up → creates tenants row
2. System creates default chart_of_accounts (based on jurisdiction template)
3. System creates first fiscal_period (current year, status=OPEN)
4. Owner receives invitation email; sets password → users row created
5. Audit log: tenant.created, user.created, period.opened
```

---

## Approval Gate

This document is a **proposal**. Implementation MUST NOT begin on any section until a human decision-maker has reviewed and explicitly approved the choices.

### Required Approvals

| Section | Decision | Approved by | Date |
|---|---|---|---|
| Stack — Backend (Python + FastAPI) | ☐ Accept ☐ Change | | |
| Stack — Frontend (Next.js) | ☐ Accept ☐ Change | | |
| Stack — Database (PostgreSQL + RLS) | ☐ Accept ☐ Change | | |
| Stack — ORM (SQLAlchemy 2 + Alembic) | ☐ Accept ☐ Change | | |
| Stack — Job Queue (Celery + Redis) | ☐ Accept ☐ Change | | |
| Stack — Object Storage (S3 / MinIO) | ☐ Accept ☐ Change | | |
| Layered architecture & dependency rule | ☐ Accept ☐ Change | | |
| Posting engine invariants (I1–I9) | ☐ Accept ☐ Change | | |
| Audit log design | ☐ Accept ☐ Change | | |
| Multi-tenant model (RLS approach) | ☐ Accept ☐ Change | | |
| RBAC role set | ☐ Accept ☐ Change | | |

### Open Questions for Reviewers

1. **Jurisdiction** — Is the default chart of accounts US-GAAP, IFRS, or jurisdiction-selectable at signup? This affects the account-seeding step in provisioning.
2. **Multi-currency v1?** — The invariants support single-currency entries. Should FX handling land in v1 or v2?
3. **Hosting target** — AWS (ECS/Fargate), Fly.io, or self-hosted? Affects which managed services we use for Redis and PostgreSQL.
4. **Payroll / payables modules** — Are these in v1 scope or integrations? Affects the chart-of-accounts template and recurring-transaction job design.
5. **Bank feed integrations** — Plaid, Finicity, or manual CSV import only for v1?
6. **Compliance requirements** — SOC 2, HIPAA, PCI? Drives logging retention, encryption at rest, and access controls.

---

*Document authored: 2026-06-06 | Branch: `docs/architecture-proposal`*
