# CairnBooks — Architecture Proposal

> **Status:** Draft · **Date:** 2026-06-05  
> **Scope:** Full-stack architecture for the CairnBooks bookkeeping application — stack selection, layer design, and core system invariants.

---

## Table of Contents

1. [Context and Goals](#1-context-and-goals)
2. [Stack Selection and Rationale](#2-stack-selection-and-rationale)
   - 2.1 [Backend — FastAPI (Python)](#21-backend--fastapi-python)
   - 2.2 [Frontend — React with TypeScript](#22-frontend--react-with-typescript)
   - 2.3 [ORM — SQLAlchemy 2.x + Alembic](#23-orm--sqlalchemy-2x--alembic)
   - 2.4 [Task Queue — Celery + Redis](#24-task-queue--celery--redis)
   - 2.5 [File Storage — S3-Compatible Object Store](#25-file-storage--s3-compatible-object-store)
   - 2.6 [Primary Database — PostgreSQL](#26-primary-database--postgresql)
3. [Layered Architecture](#3-layered-architecture)
   - 3.1 [Presentation Layer](#31-presentation-layer)
   - 3.2 [API Layer](#32-api-layer)
   - 3.3 [Application Layer](#33-application-layer)
   - 3.4 [Domain Layer](#34-domain-layer)
   - 3.5 [Data Access Layer](#35-data-access-layer)
   - 3.6 [Infrastructure Layer](#36-infrastructure-layer)
4. [System Invariants](#4-system-invariants)
5. [Cross-Cutting Concerns](#5-cross-cutting-concerns)
6. [Deployment Topology](#6-deployment-topology)
7. [Decision Log](#7-decision-log)

---

## 1. Context and Goals

CairnBooks is a double-entry bookkeeping application released under the GNU General Public License v3. Its primary goals are:

- **Correctness** — financial records must always balance; errors must be caught before they reach persistent storage.
- **Auditability** — every monetary change must be traceable to a human action or automated rule with a timestamp and actor.
- **Reliability** — data loss or silent corruption of financial records is unacceptable; the store must offer full ACID guarantees.
- **Openness** — GPL-3.0 licensing means the stack should favour free/open-source components so the entire dependency chain can be run without proprietary lock-in.

These constraints drive the choices below.

---

## 2. Stack Selection and Rationale

### 2.1 Backend — FastAPI (Python)

**Choice:** FastAPI 0.110+

**Rationale:**

- **Type-safety at the boundary.** Pydantic v2 models serve as a schema-validation layer on every request and response, catching malformed data before it reaches the domain layer. For financial data this is critical.
- **Async-first without complexity.** FastAPI's async support allows the web layer to handle concurrent requests (e.g., report generation, bulk imports) without blocking, while synchronous domain code remains straightforward to reason about.
- **Auto-generated OpenAPI documentation.** The interactive spec doubles as a living contract between frontend and backend teams, removing a common source of integration drift.
- **Python ecosystem alignment.** Python hosts the most mature financial and accounting libraries (pandas for analysis, babel for locale-aware currency formatting, python-dateutil for fiscal period arithmetic). Staying in Python avoids a language boundary for utility code.
- **Lightweight footprint.** FastAPI does not impose a full framework structure, allowing the domain layer to be organised around accounting concepts rather than framework conventions.

**Alternatives considered:**

| Alternative | Reason not chosen |
|---|---|
| Django + DRF | Rich ORM and admin are compelling for CRUD apps, but the monolithic request cycle and ORM coupling would fight a strict domain/data-access split. |
| Node.js (Express / Fastify) | Moves financial computation to a language without a mature decimal arithmetic story; `Number` floating-point precision is dangerous for money. |
| Go (Gin / Echo) | Excellent performance, but the Python ecosystem advantage for accounting utilities outweighs the speed benefit at this stage. |

---

### 2.2 Frontend — React with TypeScript

**Choice:** React 18 + TypeScript 5 + Vite

**Rationale:**

- **Component model maps to accounting UI.** Ledgers, trial balances, and income statements are naturally tabular and composable; React's declarative component model handles these patterns well.
- **TypeScript catches financial model mismatches.** Shared type definitions for `Money`, `JournalEntry`, `AccountCode`, etc. can be generated from the OpenAPI spec, ensuring the frontend and backend stay in sync.
- **Ecosystem maturity.** Headless component libraries (e.g., Radix UI), data-grid libraries (TanStack Table), and charting (Recharts) provide the building blocks for financial dashboards without mandating a heavy opinionated UI kit.
- **Vite build tooling** keeps local development iteration fast and produces lean production bundles.

**Alternatives considered:**

| Alternative | Reason not chosen |
|---|---|
| Next.js | Server-side rendering adds complexity without meaningful benefit for an authenticated financial application where all views require a logged-in session. |
| Vue 3 | Equally capable, but React's larger talent pool and wider component ecosystem tip the balance. |
| HTMX | Attractive for simplicity, but the rich interactive tables and chart views expected in bookkeeping UIs require more client-side state than HTMX handles gracefully. |

---

### 2.3 ORM — SQLAlchemy 2.x + Alembic

**Choice:** SQLAlchemy 2.0 (Core + ORM) with Alembic for migrations

**Rationale:**

- **Explicit SQL when it matters.** SQLAlchemy's dual-mode design lets the repository layer use the ORM for simple CRUD while dropping to Core expressions for complex accounting queries (running balance windows, period-close rollups) without switching libraries.
- **Unit-of-Work pattern support.** The Session abstraction maps directly to the accounting principle of an atomic transaction: all journal lines within an entry are written together or not at all.
- **Alembic migration tracking.** Schema changes are version-controlled alongside code and can be applied forward or rolled back in automated deployments.
- **PostgreSQL feature access.** SQLAlchemy 2.x exposes PostgreSQL-specific types (NUMERIC, JSONB, arrays, advisory locks) without an abstraction penalty.

**Alternatives considered:**

| Alternative | Reason not chosen |
|---|---|
| Django ORM | Tightly coupled to Django's request lifecycle; using it without Django adds more glue than it saves. |
| Tortoise ORM | Async-native but less mature; weaker support for raw SQL expressions needed for complex accounting queries. |
| Prisma (Python client) | Experimental at time of writing; not production-ready for complex schemas. |

---

### 2.4 Task Queue — Celery + Redis

**Choice:** Celery 5 with Redis as broker and result backend

**Rationale:**

- **Decoupled long-running work.** Report generation, PDF export, bank-feed reconciliation, and scheduled period-close checks must not block web request threads. Celery workers consume these tasks independently.
- **Retry semantics.** Financial background jobs (e.g., sending payment reminders, syncing with external payroll providers) need configurable retry policies with exponential back-off — Celery provides this out of the box.
- **Redis dual-role.** Redis serves as both the task broker and an application-level cache (session store, rate-limit counters), consolidating operational overhead around a single fast data structure server.
- **Beat scheduler.** Celery Beat handles recurring jobs (monthly statement generation, automated reminders) without needing a separate cron infrastructure.

**Alternatives considered:**

| Alternative | Reason not chosen |
|---|---|
| RQ (Redis Queue) | Simpler but lacks Celery's scheduling, routing, and retry sophistication needed for reliable financial background work. |
| Dramatiq | Solid alternative; Celery chosen for larger community and more documented patterns with Django/FastAPI. |
| PostgreSQL LISTEN/NOTIFY | Viable for lightweight eventing but not suited for durable task queuing or scheduled jobs at scale. |

---

### 2.5 File Storage — S3-Compatible Object Store

**Choice:** S3-compatible API (AWS S3 in production; MinIO for local and self-hosted deployments)

**Rationale:**

- **Receipt and document attachments.** Users need to attach source documents (receipts, invoices, bank statements) to journal entries. These are binary blobs that do not belong in PostgreSQL.
- **GPL compatibility.** MinIO is AGPL-3.0 and fully compatible with the project's GPL-3.0 licence for self-hosted deployments. Users who prefer AWS S3 or Cloudflare R2 can swap the endpoint with a configuration change.
- **Signed URLs for secure delivery.** Pre-signed S3 URLs allow the frontend to download attachments directly without proxying large files through the API server, keeping the API layer stateless.
- **Export artefacts.** Generated PDF reports and CSV exports are stored in object storage and served via signed URLs, avoiding filesystem state on web servers.

---

### 2.6 Primary Database — PostgreSQL

**Choice:** PostgreSQL 16+ as the **System of Record (SoR)**

**Rationale:**

PostgreSQL is the unambiguous choice for a bookkeeping application for the following reasons:

- **ACID guarantees.** Every journal entry write must be atomic. PostgreSQL's multi-version concurrency control (MVCC) provides serialisable isolation without the lock contention that would arise in financial write-heavy workloads under weaker isolation levels.
- **NUMERIC type.** PostgreSQL's arbitrary-precision `NUMERIC` type avoids the floating-point rounding errors that make `FLOAT` and `DOUBLE PRECISION` unsuitable for monetary arithmetic. Account balances and transaction amounts are stored as exact decimals.
- **Row-level security.** Multi-tenant deployments can enforce tenant data isolation at the database layer as a defence-in-depth measure, independent of application-layer access control.
- **Referential integrity.** Foreign-key constraints between `accounts`, `journal_entries`, and `journal_lines` ensure the chart of accounts stays internally consistent even if application bugs allow malformed writes.
- **Audit via triggers.** PostgreSQL triggers can maintain an immutable append-only audit log in a separate `audit_log` table, ensuring no application-layer code path can bypass the audit trail.
- **Window functions for accounting queries.** Running balance calculations, period comparisons, and ageing analyses translate directly to efficient SQL window functions without requiring application-side aggregation.
- **Open source.** PostgreSQL is permissively licensed (PostgreSQL Licence), with no conflict with GPL-3.0.

---

## 3. Layered Architecture

The application is structured in six vertical layers. Each layer may only depend on layers below it; no downward layer imports anything from a layer above it.

```
┌─────────────────────────────────────────────────────────┐
│                   Presentation Layer                    │  React SPA
├─────────────────────────────────────────────────────────┤
│                      API Layer                          │  FastAPI routers + Pydantic schemas
├─────────────────────────────────────────────────────────┤
│                  Application Layer                      │  Use-case services, auth, task dispatch
├─────────────────────────────────────────────────────────┤
│                    Domain Layer                         │  Accounting model, business rules, value objects
├─────────────────────────────────────────────────────────┤
│                 Data Access Layer                       │  Repositories, Unit of Work, query objects
├─────────────────────────────────────────────────────────┤
│                 Infrastructure Layer                    │  PostgreSQL, Redis, S3, Celery workers
└─────────────────────────────────────────────────────────┘
```

### 3.1 Presentation Layer

The React + TypeScript single-page application. Responsibilities:

- Renders the user interface: chart of accounts, journal entry forms, ledger views, trial balance, income statement, balance sheet.
- Communicates exclusively through the REST API; has no direct database or queue access.
- Manages client-side state (form drafts, pagination cursors, UI preferences) via React Query for server state and Zustand for local UI state.
- Types are generated from the OpenAPI schema at build time to keep client/server contracts in sync.

**What this layer does NOT do:** business logic, validation beyond UX convenience, or any computation that could affect financial correctness.

---

### 3.2 API Layer

FastAPI routers and Pydantic request/response models. Responsibilities:

- Defines HTTP endpoints organised by resource (`/accounts`, `/journal-entries`, `/reports`, `/periods`).
- Validates and deserialises incoming requests using Pydantic models; rejects malformed input before it reaches the application layer.
- Authenticates requests (JWT bearer tokens) and populates a request-scoped security context.
- Serialises domain objects to JSON responses; never exposes internal database row shapes directly.
- Dispatches Celery tasks for long-running operations; returns a task ID immediately so the client can poll for completion.

**What this layer does NOT do:** business logic, database queries, file I/O.

---

### 3.3 Application Layer

Use-case service classes (one class per meaningful user action). Responsibilities:

- Orchestrates multi-step workflows: validate inputs → call domain logic → persist via repositories → emit events.
- Owns transaction boundaries: opens a Unit of Work, coordinates one or more repository calls, commits or rolls back atomically.
- Enforces authorisation rules (which authenticated principal may perform which action on which resource).
- Publishes integration events (via Celery tasks) after a successful commit: e.g., `JournalEntryPosted` triggers a recalculation of cached account balances.

**What this layer does NOT do:** HTTP concerns (status codes, headers), raw SQL, direct object storage access.

---

### 3.4 Domain Layer

The heart of the application — pure Python classes representing accounting concepts. No framework dependencies. Responsibilities:

- Defines the core entities: `Account`, `JournalEntry`, `JournalLine`, `FiscalPeriod`, `LedgerBalance`, `Organisation`.
- Encapsulates invariant enforcement (see Section 4) as methods on domain objects that raise domain exceptions before any persistence occurs.
- Defines value objects: `Money` (amount + currency code), `AccountCode` (structured chart of accounts identifier), `FiscalDate`.
- Defines domain events raised by entities: `JournalEntryPosted`, `PeriodClosed`, `AccountDeactivated`.

**What this layer does NOT do:** I/O of any kind. Domain objects are plain Python; they can be unit-tested without a database, HTTP client, or message broker.

---

### 3.5 Data Access Layer

Repository classes and the Unit of Work abstraction. Responsibilities:

- Provides repository interfaces (`AccountRepository`, `JournalEntryRepository`, `FiscalPeriodRepository`) with concrete SQLAlchemy implementations.
- Implements the Unit of Work pattern: a single SQLAlchemy `Session` is shared across all repositories within one application-layer transaction, ensuring all writes commit or roll back together.
- Contains query objects for complex reads: running balance windows, ageing summaries, trial balance aggregation.
- Translates between SQLAlchemy ORM models (data-layer representations) and domain entities (domain-layer representations) to keep the layers decoupled.

**What this layer does NOT do:** business rules, HTTP concerns, direct task dispatch.

---

### 3.6 Infrastructure Layer

The operational substrate. Components:

| Component | Role |
|---|---|
| **PostgreSQL 16** | System of Record — all financial data, chart of accounts, journal entries, audit log |
| **Redis 7** | Celery broker, result backend, session cache, rate-limit counters |
| **S3-compatible store** | Document attachments, generated reports, export artefacts |
| **Celery workers** | Background tasks: report generation, reconciliation, scheduled jobs |
| **Celery Beat** | Cron-style scheduler for recurring financial jobs |
| **Alembic** | PostgreSQL schema migration runner |

---

## 4. System Invariants

These invariants are non-negotiable properties of the system. Any change to code or schema that would allow an invariant to be violated must be rejected. They are enforced at multiple layers (domain, database constraint, or both) for defence in depth.

### INV-1 — Double-Entry Balance

> For every posted journal entry, the sum of all debit amounts must equal the sum of all credit amounts.

- **Enforced at:** Domain layer (`JournalEntry.post()` raises `UnbalancedEntryError` before the entry is passed to the repository), and as a PostgreSQL constraint trigger as a backstop.

### INV-2 — Immutability of Posted Entries

> A posted journal entry's lines may never be modified or deleted. Corrections must be made by creating a reversing entry followed by a correcting entry.

- **Enforced at:** Domain layer (posted entries reject mutation calls), and database-layer row-level security / trigger that blocks `UPDATE`/`DELETE` on `journal_lines` where the parent entry has `status = 'posted'`.

### INV-3 — Closed Period Lock

> No journal entry may be created, modified, or reversed with an effective date that falls within a closed fiscal period.

- **Enforced at:** Application layer (period-status check before dispatching to the domain), and a PostgreSQL check constraint via trigger on `journal_entries.effective_date`.

### INV-4 — Monetary Precision

> All monetary values are stored and computed as exact decimals. Floating-point arithmetic is never used for money.

- **Enforced at:** Domain layer (`Money` value object uses Python `decimal.Decimal`), database layer (all amount columns are `NUMERIC(19, 4)` or wider), and Pydantic schema serialisation (amounts serialised as strings or JSON numbers with sufficient precision).

### INV-5 — Append-Only Audit Log

> Every state-changing operation on a financial record appends a row to the `audit_log` table. Rows in `audit_log` are never updated or deleted.

- **Enforced at:** PostgreSQL trigger on all financial tables (runs unconditionally, independent of application code), and the `audit_log` table has no `UPDATE`/`DELETE` grants assigned to the application database role.

### INV-6 — Account Hierarchy Consistency

> Every account belongs to exactly one account type (Asset, Liability, Equity, Revenue, Expense). The normal balance side (debit/credit) of an account is determined solely by its type and may not be overridden.

- **Enforced at:** Domain layer (`Account` entity derives `normal_balance` from `account_type`), database layer (`CHECK` constraint on `account_type` column).

### INV-7 — Tenant Isolation

> In multi-tenant deployments, no query may return data belonging to an organisation other than the one in the authenticated request context.

- **Enforced at:** Application layer (organisation ID injected into every repository call from the security context), and PostgreSQL row-level security policies as a defence-in-depth backstop.

### INV-8 — Referential Integrity of Chart of Accounts

> A journal line must reference an account that exists and is active at the time of posting. Deactivated accounts may not receive new journal lines.

- **Enforced at:** Application layer (account status check before entry creation), domain layer (entry validation), and database foreign-key constraint from `journal_lines.account_id` to `accounts.id`.

---

## 5. Cross-Cutting Concerns

### Authentication and Authorisation

- Authentication is handled via JWT bearer tokens issued on successful login. Tokens carry the user's organisation ID, user ID, and role claims.
- Authorisation uses role-based access control (RBAC) with roles such as `owner`, `accountant`, `viewer`, and `auditor`. The application layer checks role membership before executing use cases.
- API keys (long-lived tokens with limited scopes) are supported for external integrations and automated imports.

### Observability

- Structured JSON logs are emitted for every request, background task, and domain event. Log fields include `organisation_id`, `user_id`, `trace_id`, and `duration_ms`.
- Prometheus metrics are exposed at `/metrics` for request throughput, error rates, queue depth, and database pool utilisation.
- Distributed tracing (OpenTelemetry) instruments the API, application, and data access layers so a single user action can be traced end-to-end including Celery tasks.

### Error Handling

- Domain exceptions (e.g., `UnbalancedEntryError`, `ClosedPeriodError`) are distinct from infrastructure exceptions (e.g., `DatabaseConnectionError`). The API layer maps domain exceptions to 4xx HTTP responses and infrastructure exceptions to 5xx responses.
- Celery tasks use dead-letter queues to capture jobs that have exhausted retries, preventing silent data loss on background failures.

### Internationalisation

- Currency handling is locale-aware. The `Money` value object carries an ISO 4217 currency code. Display formatting is delegated to the frontend using the browser locale.
- Multi-currency transactions record the original currency, original amount, exchange rate, and the home-currency equivalent at the time of the transaction. Exchange rates are not retroactively updated.

---

## 6. Deployment Topology

```
                    ┌──────────────┐
                    │   Browser    │
                    └──────┬───────┘
                           │ HTTPS
                    ┌──────▼───────┐
                    │  CDN / Edge  │  Static React assets
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  API Server  │  FastAPI (uvicorn)
                    │  (1..N pods) │
                    └──┬──────┬────┘
                       │      │
          ┌────────────▼─┐  ┌─▼────────────┐
          │  PostgreSQL  │  │    Redis      │
          │  (primary +  │  │  (broker +   │
          │   replica)   │  │   cache)     │
          └──────────────┘  └─────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │  Celery Workers │
                         │  + Celery Beat  │
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │  Object Store   │
                         │  (S3 / MinIO)   │
                         └─────────────────┘
```

For self-hosted deployments, all components run via Docker Compose with MinIO replacing S3. For production SaaS deployments, managed services (AWS RDS for PostgreSQL, ElastiCache for Redis, S3) reduce operational burden.

---

## 7. Decision Log

| ID | Decision | Date | Status |
|---|---|---|---|
| ADR-001 | PostgreSQL selected as System of Record | 2026-06-05 | Accepted |
| ADR-002 | FastAPI chosen over Django for the backend | 2026-06-05 | Accepted |
| ADR-003 | SQLAlchemy 2.x + Alembic for ORM and migrations | 2026-06-05 | Accepted |
| ADR-004 | Celery + Redis for async task queue | 2026-06-05 | Accepted |
| ADR-005 | S3-compatible API for object storage | 2026-06-05 | Accepted |
| ADR-006 | React + TypeScript for the frontend SPA | 2026-06-05 | Accepted |
| ADR-007 | Domain layer must be pure Python with no I/O dependencies | 2026-06-05 | Accepted |
| ADR-008 | `NUMERIC(19,4)` minimum precision for all monetary amounts | 2026-06-05 | Accepted |
