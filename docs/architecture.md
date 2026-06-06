# CairnBooks — Architecture Proposal

**Status:** Proposed  
**Date:** 2026-06-06  
**Revision:** 1.0

---

## Table of Contents

1. [Overview & Goals](#1-overview--goals)
2. [Stack Selection](#2-stack-selection)
3. [Layered Architecture](#3-layered-architecture)
4. [PostgreSQL as System of Record](#4-postgresql-as-system-of-record)
5. [Immutability & Audit](#5-immutability--audit)
6. [Multi-Tenant Data Model](#6-multi-tenant-data-model)
7. [API-First Design](#7-api-first-design)
8. [Invariants](#8-invariants)
9. [Deployment Topology](#9-deployment-topology)
10. [Decision Log](#10-decision-log)

---

## 1. Overview & Goals

CairnBooks is an open-source, multi-tenant bookkeeping and accounting platform built for small-to-medium businesses and accountants managing multiple client books. The name "cairn" evokes the stone markers that reliably indicate position over long time horizons — a fitting metaphor for financial records that must be trustworthy, immutable, and always locatable by auditors.

### Core Design Goals

| Goal | Description |
|------|-------------|
| **Correctness first** | Financial data must be internally consistent at all times. Double-entry invariants enforced in the database layer, not only in application code. |
| **Full auditability** | Every state change is recorded with actor, timestamp, and prior value. Nothing is ever silently overwritten. |
| **Multi-tenancy** | Many organisations (tenants) share one deployment with strict data isolation enforced at the database layer. |
| **API-first** | All product capabilities are exposed as a versioned HTTP API before any UI is built against them. The UI is a first-party client of that API. |
| **Operational simplicity** | Default deployment fits on a single server; horizontal scaling is possible without architectural changes. |
| **Open ecosystem** | GPL-3 license; standard protocols (OpenAPI, OAuth2, SMTP, S3-compatible storage) so operators can swap components. |

---

## 2. Stack Selection

### 2.1 Backend — Python 3.12 + FastAPI

**Choice:** Python 3.12 with [FastAPI](https://fastapi.tiangolo.com/)

**Rationale:**

- **Domain fit.** Python has the richest ecosystem of financial and accounting libraries (`python-accounting`, `babel` for locale-aware money formatting, `pypdf` / `reportlab` for statement generation, `decimal` module for arbitrary-precision arithmetic). Accounting is a precision domain — Python's `Decimal` type avoids the rounding errors endemic to IEEE 754 floats used by default in JavaScript and Go.
- **API ergonomics.** FastAPI generates an OpenAPI 3.1 spec automatically from Python type annotations. Every endpoint is self-documenting with zero extra work, satisfying the API-first goal from day one.
- **Async I/O.** FastAPI runs on [Uvicorn](https://www.uvicorn.org/) (ASGI), enabling `asyncio`-native DB queries and external HTTP calls without blocking threads. A single process handles many concurrent connections efficiently.
- **Pydantic v2.** Request/response validation via Pydantic is built into FastAPI. Pydantic v2 (Rust-backed) is fast and forces explicit schemas at every API boundary — essential for a financial product where malformed input must be rejected loudly.
- **Ecosystem maturity.** Alembic migrations, SQLAlchemy ORM, Celery, pytest, and mypy all have first-class Python support. The toolchain is well-understood and easy to hire for.

**Considered and rejected:**

| Alternative | Reason not chosen |
|---|---|
| Go + Gin | Excellent runtime performance, but smaller accounting library ecosystem; verbose error handling increases risk of silent numeric bugs; slower initial development velocity for a greenfield project |
| Node.js + NestJS | Floating-point arithmetic hazards with `number` type; requires careful use of `big.js` or similar throughout; less mature ORM options for complex accounting queries |
| Django + DRF | Django is a solid choice, but its synchronous-by-default ORM (pre-4.2 async support is incomplete) and opinionated project layout slow down the move to a clean layered architecture |

---

### 2.2 Frontend — Next.js 14 (React + TypeScript)

**Choice:** [Next.js 14](https://nextjs.org/) with React 18 and TypeScript 5

**Rationale:**

- **TypeScript end-to-end.** Sharing generated TypeScript types from the OpenAPI spec (via `openapi-typescript`) gives compile-time safety at the API boundary — crucial for a financial UI where a mistyped amount field must never reach the server.
- **App Router + Server Components.** Next.js App Router allows server-side rendering for initial page loads (important for dashboard pages with large data sets) while staying fully interactive on the client.
- **API co-location.** Next.js Route Handlers can serve as a lightweight backend-for-frontend (BFF) layer, handling cookie-based session management and per-request tenant context injection without requiring the React code to manage raw JWT headers.
- **Ecosystem.** React has the largest component library ecosystem. Accounting UIs need tables, charts, date pickers, and currency inputs — all well-served by Radix UI, shadcn/ui, Recharts, and similar.
- **Incremental adoption.** Pages can be added one at a time; existing routes are unaffected. This fits a team shipping features iteratively.

**Considered and rejected:**

| Alternative | Reason not chosen |
|---|---|
| SvelteKit | Smaller ecosystem for complex data-grid components needed in accounting UIs; smaller hiring pool |
| Vue 3 + Nuxt | Strong choice, but TypeScript integration slightly less seamless than React/Next.js for large codebases |
| Plain React (Vite SPA) | No built-in SSR; harder to protect sensitive routes; requires separate solution for BFF concerns |

---

### 2.3 ORM — SQLAlchemy 2.0 (async) + Alembic

**Choice:** [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/) with `asyncpg` driver and [Alembic](https://alembic.sqlalchemy.org/) migrations

**Rationale:**

- **Async-native.** SQLAlchemy 2.0 introduced a full async ORM via `AsyncSession`. Combined with `asyncpg` (a pure-Python async PostgreSQL driver), queries never block the event loop.
- **Raw SQL escape hatch.** SQLAlchemy Core allows dropping to raw SQL with parameter binding for complex reporting queries (rolling balances, trial balance, aged receivables) without losing parameterisation safety.
- **Schema migrations.** Alembic generates migration scripts from model diffs, with support for multi-branch scenarios. Migrations are plain Python — reviewable, testable, and reversible.
- **PostgreSQL-specific features.** SQLAlchemy exposes PostgreSQL dialects for `JSONB`, `UUID`, `ARRAY`, range types, and advisory locks — all used in the data model below.

---

### 2.4 Job Queue — Celery 5 + Redis

**Choice:** [Celery 5](https://docs.celeryq.dev/) with Redis as broker and result backend

**Rationale:**

- **Maturity.** Celery is the standard Python background task library with a decade of production hardening.
- **Rich feature set.** Rate limiting, task retries with exponential back-off, task chaining and chords (needed for multi-step report generation pipelines), periodic tasks via Celery Beat (for recurring billing, scheduled reports, payment reminders).
- **Redis as broker.** Redis is already present in the stack for caching API responses and session storage. Using it as the Celery broker avoids a second message queue dependency for most deployments. For high-volume workloads, the broker can be swapped to RabbitMQ without changing task code.
- **Flower monitoring.** Celery ships a first-party web monitor (Flower) that shows task status, retries, and worker health with no extra instrumentation.

**Use cases:**
- PDF statement and tax report generation
- Bulk import/export (CSV, OFX, QIF)
- Scheduled reconciliation checks
- Email and webhook notification dispatch
- Recurring transaction and invoice generation

---

### 2.5 Object Storage — S3-Compatible (AWS S3 / MinIO)

**Choice:** S3-compatible object storage, defaulting to [MinIO](https://min.io/) for self-hosted deployments and AWS S3 for cloud deployments

**Rationale:**

- **S3 protocol is a de-facto standard.** Every cloud provider (AWS, GCP, Azure, Cloudflare R2, Backblaze B2) and every self-hosted solution (MinIO, SeaweedFS, Garage) speaks the S3 API. CairnBooks uses the `boto3` / `aiobotocore` client with a configurable endpoint URL — operators swap storage backends by changing an environment variable.
- **Separation of concerns.** Binary objects (uploaded receipts, exported PDFs, bank statement files) do not belong in PostgreSQL. Keeping them in object storage avoids table bloat and allows CDN distribution of generated assets.
- **Presigned URLs.** S3 presigned URLs let the frontend download files directly from storage without proxying through the application server, reducing bandwidth costs.
- **Versioning.** S3 bucket versioning preserves every version of a stored document, supporting the immutability goal for uploaded source documents.

**Stored objects:**
- Receipt and invoice scans (JPEG, PNG, PDF)
- Generated PDF statements and reports
- Bulk import files (CSV, OFX, QIF) pending processing
- Database export snapshots

---

## 3. Layered Architecture

CairnBooks uses a four-layer architecture with strict one-way dependency flow. Each layer may only import from the layer immediately below it.

```
┌──────────────────────────────────────────────────────────────────────┐
│  Presentation Layer                                                   │
│  Next.js 14 (React + TypeScript)                                     │
│  · Server Components for initial render                              │
│  · Client Components for interactive widgets                         │
│  · BFF Route Handlers for cookie/session management                  │
└────────────────────────┬─────────────────────────────────────────────┘
                         │  HTTPS / REST  (OpenAPI 3.1)
┌────────────────────────▼─────────────────────────────────────────────┐
│  API Layer                                                            │
│  FastAPI (Uvicorn / ASGI)                                            │
│  · Route handlers — thin, no business logic                          │
│  · Request/response validation via Pydantic v2 schemas               │
│  · Authentication middleware (JWT + OAuth2)                          │
│  · Tenant context injection (extracts org_id from JWT)               │
│  · OpenAPI spec auto-generation                                      │
│  · API versioning (/api/v1/, /api/v2/)                               │
└────────────────────────┬─────────────────────────────────────────────┘
                         │  Python function calls only
┌────────────────────────▼─────────────────────────────────────────────┐
│  Service Layer                                                        │
│  Pure Python — no framework imports                                  │
│  · Orchestrates use cases (post journal entry, create invoice, …)    │
│  · Enforces double-entry invariants before writing                   │
│  · Emits domain events to the event bus                              │
│  · Calls Repository interfaces — never touches SQLAlchemy directly   │
│  · Owns transaction boundaries (unit of work pattern)                │
└────────────────────────┬─────────────────────────────────────────────┘
                         │  Repository / Port interfaces
┌────────────────────────▼─────────────────────────────────────────────┐
│  Infrastructure Layer                                                 │
│  · SQLAlchemy 2.0 repository implementations                         │
│  · PostgreSQL (asyncpg)                                              │
│  · Redis (caching, sessions, Celery broker)                          │
│  · Celery workers + Beat scheduler                                   │
│  · S3-compatible object storage (boto3 / aiobotocore)                │
│  · SMTP / transactional email provider                               │
└──────────────────────────────────────────────────────────────────────┘
```

### Layer Contracts

| Boundary | Allowed | Forbidden |
|----------|---------|-----------|
| Presentation → API | HTTP requests with JSON bodies | Direct DB access, importing service modules |
| API → Service | Call service functions; pass validated Pydantic models | SQLAlchemy models, raw SQL |
| Service → Infrastructure | Call repository methods; use defined port interfaces | HTTP calls, framework objects, direct Redis access |
| Infrastructure ← Service | Implement repository interfaces; manage DB sessions | Business logic, validation rules |

### Dependency Inversion

The Service Layer depends on **abstract repository interfaces** (Python `Protocol` classes), not on SQLAlchemy. This means:
- Services are tested with in-memory fakes without a database.
- The PostgreSQL implementation can be replaced (e.g., during testing or for a read replica) without touching service code.
- The same service function handles both online API requests and background Celery tasks.

---

## 4. PostgreSQL as System of Record

PostgreSQL is the **sole authoritative source of truth** for all financial state. No other store (Redis cache, Elasticsearch index, object storage) is consulted to determine account balances, transaction history, or entity state. Derived views in other systems are considered caches and are always reconstructible from PostgreSQL.

### Why PostgreSQL is Sufficient

| Need | PostgreSQL feature |
|------|--------------------|
| ACID transactions | Full serialisable isolation for double-entry posting |
| Concurrent access | MVCC — readers never block writers |
| Referential integrity | Foreign key constraints with `DEFERRABLE` for batch inserts |
| Row-level security | RLS policies enforce tenant isolation at engine level |
| Audit history | Trigger-based audit tables + append-only ledger tables |
| Reporting | Window functions, CTEs, `LATERAL` joins for running totals |
| Full-text search | `tsvector` / `tsquery` for ledger entry narration search |
| JSON metadata | `JSONB` columns for extensible line-item metadata |
| Concurrency control | Advisory locks for sequential invoice numbering |
| Scheduled tasks | `pg_cron` for lightweight recurring DB maintenance jobs |

### PostgreSQL Configuration Recommendations

```
# postgresql.conf (production baseline)
max_connections        = 100          # Use PgBouncer for connection pooling
shared_buffers         = 25% of RAM
wal_level              = logical      # enables logical replication for read replicas
wal_compression        = on
synchronous_commit     = on           # never relax for financial data
log_checkpoints        = on
log_connections        = on
log_min_duration_statement = 1000ms  # log slow queries
```

### Connection Pooling

PgBouncer in **transaction mode** sits between the application and PostgreSQL, keeping `max_connections` manageable while supporting hundreds of concurrent application workers.

### Read Replicas

Long-running reporting queries (trial balance, aged receivables, VAT return) run against a streaming replication **read replica** to avoid contention with OLTP writes. The application selects the replica connection via a repository method flag (`read_only=True`).

---

## 5. Immutability & Audit

### 5.1 Immutability Model

CairnBooks treats financial records as **immutable ledger entries** once they have been posted. This is the accounting standard approach and is required for audit compliance.

**Rules:**

1. **No UPDATE on posted journal entries.** The `journal_lines` and `journal_headers` tables have a PostgreSQL trigger that raises an exception on `UPDATE` or `DELETE` of any row whose `status = 'POSTED'`.
2. **Correction via reversal.** To correct a posted entry, a service creates a reversing entry (equal and opposite debits/credits) and then posts the corrected entry. Both the reversal and the correction are new rows linked to the original via `reversed_by_id` / `corrects_id` foreign keys.
3. **Voiding** marks an entry `status = 'VOID'` and creates a reversal in the same period. The void status is itself immutable once set.
4. **Soft-delete prohibition.** Financial entity tables (accounts, contacts, journals) have no `deleted_at` column. Deactivation is modelled as a status change to `INACTIVE`, which is audited.

### 5.2 Append-Only Audit Log

Every mutation of any table is captured in an `audit_log` table via a generalised PostgreSQL trigger function.

```sql
CREATE TABLE audit_log (
    id            BIGSERIAL PRIMARY KEY,
    org_id        UUID        NOT NULL,           -- tenant
    table_name    TEXT        NOT NULL,
    row_id        TEXT        NOT NULL,           -- PK of affected row (cast to text)
    operation     TEXT        NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
    actor_id      UUID,                           -- NULL for system/migration actions
    actor_type    TEXT        NOT NULL DEFAULT 'user',  -- 'user' | 'system' | 'celery'
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    old_values    JSONB,                          -- NULL for INSERT
    new_values    JSONB,                          -- NULL for DELETE
    ip_address    INET,
    user_agent    TEXT
);

-- Partition by month for query performance
CREATE INDEX ON audit_log (org_id, table_name, occurred_at DESC);
```

The trigger is applied to all domain tables:

```sql
CREATE TRIGGER audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON journal_headers
FOR EACH ROW EXECUTE FUNCTION record_audit_event();
```

The `record_audit_event()` function records `old_values` and `new_values` as `JSONB` snapshots, strips any columns in a per-table exclusion list (e.g., cached denormalised columns), and writes to `audit_log`. The `audit_log` table itself has a trigger that raises an error on `UPDATE` or `DELETE` — the audit log is **always append-only**.

### 5.3 Application-Level Audit Events

Beyond the database trigger, the Service Layer emits structured **domain events** for business-significant actions:

```python
@dataclass
class JournalPostedEvent:
    org_id: UUID
    journal_id: UUID
    posted_by: UUID
    posted_at: datetime
    total_debit: Decimal
    total_credit: Decimal
```

These events are written to a `domain_events` table (also append-only) and optionally forwarded to a webhook endpoint configured per tenant.

---

## 6. Multi-Tenant Data Model

### 6.1 Tenancy Strategy: Shared Database, Row-Level Security

CairnBooks uses a **single database with row-level security (RLS)** to isolate tenants. Every tenant-scoped table carries an `org_id UUID NOT NULL` column, and PostgreSQL RLS policies ensure that a connection authenticated as one tenant cannot read or write rows belonging to another.

**Why not schema-per-tenant?**

| Concern | Shared DB + RLS | Schema-per-tenant |
|---------|----------------|-------------------|
| Isolation strength | Enforced by PostgreSQL kernel | Same (different schemas, same DB) |
| Migration complexity | One Alembic migration runs once | Must run against every tenant schema |
| Connection pooling | PgBouncer works naturally | Each tenant needs its own pool target |
| Cross-tenant queries | Simple (admin sets `app.current_org_id = NULL`) | Requires UNION across schemas |
| Operational overhead | Low | Grows linearly with tenant count |

Schema-per-tenant is appropriate when tenants have contractual data residency requirements or when tenant schemas must diverge. CairnBooks provides a migration path to a dedicated schema or database for enterprise tenants, but ships with the shared model.

### 6.2 RLS Policy Pattern

```sql
-- Every table sets this policy
ALTER TABLE journal_headers ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_headers FORCE ROW LEVEL SECURITY;   -- affects table owner too

CREATE POLICY tenant_isolation ON journal_headers
    USING (org_id = current_setting('app.current_org_id')::uuid);
```

The application sets `app.current_org_id` at the start of every database transaction via the repository layer:

```python
async def set_tenant_context(session: AsyncSession, org_id: UUID) -> None:
    await session.execute(
        text("SET LOCAL app.current_org_id = :org_id"),
        {"org_id": str(org_id)},
    )
```

`SET LOCAL` scopes the setting to the current transaction, so it is automatically cleared when the transaction commits or rolls back — tenant context never leaks between requests even when using connection pooling.

### 6.3 Core Tenant Tables

```
organisations          -- root tenant entity (billing, plan, settings)
  │
  ├── org_users        -- membership and roles (OWNER, ADMIN, BOOKKEEPER, VIEWER)
  ├── org_invitations  -- pending invites (time-limited tokens)
  │
  ├── chart_of_accounts
  │     └── accounts   -- asset, liability, equity, revenue, expense
  │
  ├── fiscal_years
  │     └── accounting_periods  -- open/closed status
  │
  ├── contacts         -- customers, suppliers, employees
  │
  ├── journal_headers  -- transaction envelope (date, reference, narration)
  │     └── journal_lines  -- debit/credit lines (account, amount, currency)
  │
  ├── invoices         -- AR invoice lifecycle
  │     └── invoice_lines
  │
  ├── bills            -- AP bill lifecycle
  │     └── bill_lines
  │
  ├── payments         -- payment records linked to invoices/bills
  │
  ├── bank_accounts
  │     └── bank_transactions  -- imported/reconciled transactions
  │
  ├── tax_rates
  │     └── tax_components
  │
  └── attachments      -- links to object storage keys
```

### 6.4 Organisation Table

```sql
CREATE TABLE organisations (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          TEXT        NOT NULL UNIQUE,
    display_name  TEXT        NOT NULL,
    country_code  CHAR(2)     NOT NULL,
    currency_code CHAR(3)     NOT NULL,
    plan          TEXT        NOT NULL DEFAULT 'free',
    status        TEXT        NOT NULL DEFAULT 'active',
    settings      JSONB       NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 6.5 Double-Entry Integrity Constraint

The database enforces that journal entries balance at the database level, not only in application code:

```sql
-- Enforced by a deferred constraint trigger on journal_headers
-- Fires at end of transaction to allow multi-row inserts in one batch
CREATE CONSTRAINT TRIGGER check_journal_balance
AFTER INSERT OR UPDATE ON journal_lines
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION verify_journal_balance();
```

The trigger function raises `RAISE EXCEPTION` if `SUM(debit_amount) != SUM(credit_amount)` for the journal being committed.

### 6.6 Currency Handling

All monetary amounts are stored as `NUMERIC(19,6)` — no `FLOAT` or `DOUBLE PRECISION` columns exist in the financial schema. The 6 decimal places accommodate cryptocurrencies and currencies with minor-unit subdivisions. Application-layer `Decimal` objects are serialised directly to PostgreSQL `NUMERIC`; no floating-point conversion occurs at any point.

---

## 7. API-First Design

### 7.1 Principles

- **All features via API.** No functionality is reachable only through the UI. Every action the Next.js frontend can perform is also available to API consumers and Celery workers via the same endpoint.
- **Versioned routes.** The URL prefix `/api/v1/` is frozen once released. Breaking changes require `/api/v2/`. Non-breaking additions (new optional fields, new endpoints) are added to the current version.
- **OpenAPI 3.1 spec.** FastAPI generates the spec from code annotations. The spec is published at `/api/v1/openapi.json` and rendered at `/api/docs` (Swagger UI) and `/api/redoc`. The spec is committed to the repo on each release and used to generate the TypeScript client.
- **Pagination.** All list endpoints use cursor-based pagination (`after`, `before`, `limit`) rather than offset pagination, to avoid skipped or duplicated rows when records are inserted between pages.
- **Idempotency.** Mutating endpoints accept an `Idempotency-Key` header. The server stores results keyed by `(org_id, idempotency_key)` for 24 hours, returning the cached response for replays. This is essential for financial operations (posting a journal entry twice must not double-count).
- **Problem Details.** Errors follow [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) (`application/problem+json`) with machine-readable `type` URIs.

### 7.2 Authentication & Authorisation

```
Auth flow:
  Browser → POST /api/v1/auth/login    → {access_token, refresh_token}
  Browser → GET  /api/v1/accounts      → Authorization: Bearer <access_token>

Token structure (JWT):
  {
    "sub":   "<user_id>",
    "org":   "<org_id>",
    "roles": ["BOOKKEEPER"],
    "exp":   <unix_ts>,
    "jti":   "<token_id>"    // for revocation
  }
```

- Access tokens expire in 15 minutes; refresh tokens in 30 days.
- Token revocation list stored in Redis (checked on every request via middleware).
- Roles are checked by the Service Layer, not the API Layer, so Celery tasks and CLI tools enforce the same rules.
- OAuth2 / OIDC provider integration (Google, Microsoft) is supported via the `org_users.identity_provider` column.

### 7.3 Tenant Context in the API

The JWT carries `org_id`. The API middleware:
1. Validates the JWT signature and expiry.
2. Checks the revocation list.
3. Verifies the user is an active member of the claimed org.
4. Sets `app.current_org_id` on the database transaction (see §6.2).
5. Injects `org_id` and `actor_id` into the service call context.

### 7.4 Rate Limiting

Per-org rate limits are enforced by a Redis sliding-window counter in the API middleware:

| Plan | Requests/minute | Burst |
|------|----------------|-------|
| Free | 60 | 20 |
| Pro | 600 | 100 |
| Enterprise | 6000 | 500 |

### 7.5 Webhooks

Tenants configure webhook endpoints to receive `domain_events` in real time. The Celery worker delivers events with HMAC-SHA256 signatures and retries with exponential back-off up to 72 hours.

---

## 8. Invariants

These invariants must hold at all times and are enforced at both the application layer (service-level assertions) and the database layer (constraints, triggers). Any code path that would violate an invariant must raise an error before committing.

### I-1: Double-Entry Balance

> For every posted journal entry, the sum of all debit amounts equals the sum of all credit amounts, in each currency.

**Enforced by:** Deferred constraint trigger `check_journal_balance` on `journal_lines` (see §6.5). The Service Layer also asserts this before submitting the transaction.

### I-2: Tenant Isolation

> No query executed on behalf of tenant A may return, modify, or reference rows belonging to tenant B.

**Enforced by:** PostgreSQL RLS policies on all tenant-scoped tables. `FORCE ROW LEVEL SECURITY` ensures the policy applies even to the table owner role. `SET LOCAL app.current_org_id` is set in every transaction before any query is executed.

### I-3: Immutability of Posted Entries

> Rows in `journal_headers` and `journal_lines` with `status = 'POSTED'` may not be updated or deleted.

**Enforced by:** `BEFORE UPDATE OR DELETE` trigger raises `RAISE EXCEPTION` if the row being modified has `status = 'POSTED'`. Corrections are made via reversal entries only.

### I-4: Closed Period Protection

> No journal entry may be posted into a closed accounting period.

**Enforced by:** Service Layer checks `accounting_periods.status = 'OPEN'` for the entry date before posting. The database has a trigger on `journal_headers` that verifies this against the `accounting_periods` table.

### I-5: Monetary Precision

> All monetary amounts are stored as `NUMERIC(19,6)`. No column in the financial schema may use `FLOAT`, `REAL`, or `DOUBLE PRECISION`.

**Enforced by:** A CI check (`scripts/check_schema_types.py`) scans Alembic migrations and raises an error if a floating-point column type appears in any financial table. Code review policy documents this requirement.

### I-6: Audit Log Append-Only

> Rows in `audit_log` and `domain_events` may never be updated or deleted.

**Enforced by:** `BEFORE UPDATE OR DELETE` trigger on both tables raises an unconditional exception. The application role does not have `UPDATE` or `DELETE` privilege on these tables.

### I-7: Idempotency

> Submitting the same mutating API request twice with the same `Idempotency-Key` produces one state change, not two.

**Enforced by:** Idempotency key table with `UNIQUE (org_id, idempotency_key)` constraint. The service layer checks for an existing result before executing the operation.

### I-8: Currency Consistency

> All journal lines within a single journal entry in the base (reporting) currency must net to zero.

**Enforced by:** The balance trigger (I-1) operates per-currency. Multi-currency entries include both the transaction-currency lines and the corresponding base-currency conversion lines.

---

## 9. Deployment Topology

### 9.1 Single-Server (Default)

Suitable for self-hosted deployments and development:

```
┌─────────────────────────────────────────────────────┐
│  Linux server (Ubuntu 24.04 LTS)                   │
│                                                     │
│  ┌────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Caddy     │  │  Next.js     │  │  FastAPI   │  │
│  │  (TLS,     │→ │  (Node 20)   │  │  (Uvicorn) │  │
│  │  reverse   │  │  :3000       │  │  :8000     │  │
│  │  proxy)    │  └──────────────┘  └─────┬──────┘  │
│  └────────────┘                          │          │
│                                          │          │
│  ┌─────────────────────────┐  ┌──────────▼───────┐  │
│  │  PostgreSQL 16          │  │  Redis 7         │  │
│  │  (primary)              │  │  (cache, broker) │  │
│  └─────────────────────────┘  └──────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  Celery workers (2 processes) + Beat         │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  MinIO (object storage, S3-compatible)       │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

All components run as systemd services or Docker containers managed by Docker Compose.

### 9.2 Cloud / Scaled Deployment

For SaaS or high-availability operation:

```
CDN (Cloudflare)
  │
  ├── Next.js: Vercel / AWS ECS (stateless, horizontally scaled)
  │
  └── FastAPI: AWS ECS / Kubernetes
        │
        ├── PostgreSQL: AWS RDS (primary) + read replica for reporting
        ├── Redis: AWS ElastiCache
        ├── Celery workers: ECS / k8s deployment (auto-scaled)
        └── Object storage: AWS S3
```

### 9.3 Environment Configuration

All configuration is via environment variables (12-factor app). No secrets in code or config files:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL DSN (asyncpg format) |
| `DATABASE_READ_URL` | Read-replica DSN (optional) |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing key (HS256 or RS256 public key path) |
| `S3_ENDPOINT_URL` | Object storage endpoint (blank = AWS S3) |
| `S3_BUCKET` | Bucket name for uploads |
| `AWS_ACCESS_KEY_ID` | S3 credentials |
| `AWS_SECRET_ACCESS_KEY` | S3 credentials |
| `SMTP_URL` | `smtp://user:pass@host:587` |
| `APP_BASE_URL` | Public URL (for webhook callbacks, email links) |
| `ALLOWED_ORIGINS` | CORS origin list |

---

## 10. Decision Log

| Date | Decision | Alternatives considered | Rationale |
|------|----------|------------------------|-----------|
| 2026-06-06 | Python + FastAPI for backend | Go/Gin, Node/NestJS, Django | Financial library ecosystem; Pydantic validation; OpenAPI auto-gen |
| 2026-06-06 | Next.js 14 for frontend | SvelteKit, Vue/Nuxt, Vite SPA | TypeScript ecosystem; SSR; BFF pattern |
| 2026-06-06 | SQLAlchemy 2.0 + asyncpg | Tortoise ORM, Django ORM | Async native; raw SQL escape hatch; Alembic migrations |
| 2026-06-06 | Celery + Redis for job queue | ARQ, Dramatiq, RQ | Maturity; Celery Beat for scheduling; Flower monitoring |
| 2026-06-06 | S3-compatible object storage | PostgreSQL large objects, local disk | Protocol portability; presigned URLs; versioning |
| 2026-06-06 | Shared DB + RLS multi-tenancy | Schema-per-tenant, DB-per-tenant | Migration simplicity; connection pooling; cross-tenant admin queries |
| 2026-06-06 | `NUMERIC(19,6)` for money | BIGINT cents, FLOAT | Exact decimal arithmetic; no rounding errors; supports crypto |
| 2026-06-06 | Cursor-based pagination | Offset/limit | Consistency under concurrent inserts/deletes |
| 2026-06-06 | Deferred constraint trigger for balance | Application-only check | Cannot be bypassed by direct DB inserts or bulk loaders |

---

*This document is the living architecture record for CairnBooks. Significant deviations from this proposal should be recorded in the Decision Log with rationale.*
