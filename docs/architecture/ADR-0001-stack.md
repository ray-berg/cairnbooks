# ADR-0001: Technology Stack Selection

| Field         | Value                                     |
|---------------|-------------------------------------------|
| Status        | **Accepted**                              |
| Date          | 2026-06-07                                |
| Deciders      | Architecture Team                         |
| Supersedes    | —                                         |
| Superseded by | —                                         |

---

## Table of Contents

1. [Context](#1-context)
2. [Decision](#2-decision)
3. [Stack Rationale](#3-stack-rationale)
   - 3.1 [Backend — Python 3.12 + FastAPI](#31-backend--python-312--fastapi)
   - 3.2 [ORM & Migrations — SQLAlchemy 2 + Alembic](#32-orm--migrations--sqlalchemy-2--alembic)
   - 3.3 [Database — PostgreSQL 16](#33-database--postgresql-16)
   - 3.4 [Background Jobs — RQ / Arq](#34-background-jobs--rq--arq)
   - 3.5 [Frontend — React + Vite + Tailwind CSS](#35-frontend--react--vite--tailwind-css)
   - 3.6 [Object Storage — MinIO / S3-compatible](#36-object-storage--minio--s3-compatible)
4. [Layered Architecture](#4-layered-architecture)
   - 4.1 [Layer Map](#41-layer-map)
   - 4.2 [Layer Responsibilities](#42-layer-responsibilities)
   - 4.3 [Dependency Rule](#43-dependency-rule)
   - 4.4 [Module Layout](#44-module-layout)
5. [Consequences](#5-consequences)
6. [Alternatives Considered](#6-alternatives-considered)

---

## 1. Context

CairnBooks is an open-source, double-entry accounting platform for small businesses. It must:

- Guarantee **ACID integrity** across every journal entry (debits must equal credits, always).
- Support **multi-tenancy** — each company's books are strictly isolated at the data layer.
- Be **API-first**: every capability is exposed over HTTPS so third-party integrations, mobile
  clients, and the first-party React UI are all equal consumers of the same endpoints.
- Be **runnable locally** via a single `docker compose up` and deployable to a production
  Proxmox LXC without proprietary cloud requirements.
- Remain **open-source and self-hostable**: no hard dependencies on any paid cloud service.

These constraints drive every stack choice below.

---

## 2. Decision

CairnBooks adopts the following technology stack:

| Concern              | Choice                                   | Version  |
|----------------------|------------------------------------------|----------|
| Backend language     | Python                                   | 3.12+    |
| Backend framework    | FastAPI                                  | 0.115+   |
| ORM                  | SQLAlchemy 2                             | 2.x      |
| Schema migrations    | Alembic                                  | 1.x      |
| Relational database  | PostgreSQL                               | 16+      |
| Background jobs      | RQ (Redis Queue) **or** Arq              | latest   |
| Job broker / cache   | Redis                                    | 7.x      |
| Frontend framework   | React (Vite bundler)                     | 18+ / 5+ |
| Frontend styling     | Tailwind CSS                             | 3.x      |
| Object storage       | MinIO (dev) / S3-compatible (prod)       | —        |
| Authentication       | JWT access + refresh tokens              | —        |
| Container runtime    | Docker + Docker Compose                  | —        |
| Reverse proxy        | Caddy 2                                  | 2.x      |

---

## 3. Stack Rationale

### 3.1 Backend — Python 3.12 + FastAPI

**Why Python?**

Accounting correctness requires exact decimal arithmetic. Python's `decimal.Decimal` type with
configurable precision is the de-facto standard for financial calculation in the open-source
ecosystem (GnuCash, Beancount, Ledger-CLI). The language has mature libraries for PDF
generation, CSV/OFX import, tax computation, and bank-feed parsing — all MVP requirements.

**Why FastAPI?**

| Criterion                     | FastAPI      | Django REST  | Flask        |
|-------------------------------|--------------|--------------|--------------|
| Async-first (`asyncio`)       | ✅ Built-in  | ❌ Optional  | ❌ Optional  |
| Auto-generated OpenAPI docs   | ✅ Built-in  | Plugin       | Plugin       |
| Pydantic v2 validation        | ✅ Built-in  | Third-party  | Third-party  |
| Throughput vs DRF baseline    | ~2×          | 1× (baseline)| ~1.5×        |
| Explicit ORM choice           | ✅ Yes       | ❌ Forces Django ORM | ✅ Yes |

FastAPI's Pydantic v2 layer schema-validates every request and response, producing a reliable
OpenAPI 3.1 specification. That spec is the contract from which the React client's TypeScript
types are generated, eliminating an entire class of frontend/backend type-mismatch bugs.

Django REST Framework is excluded because it couples to the Django ORM (we use SQLAlchemy for
explicit transaction control) and ships an admin UI that duplicates effort. Flask lacks the
async primitives needed for WebSocket support (real-time dashboard notifications).

---

### 3.2 ORM & Migrations — SQLAlchemy 2 + Alembic

**Why SQLAlchemy 2?**

SQLAlchemy 2's `Mapped` / `mapped_column` annotation API provides:

- **Explicit session and transaction control** — critical for double-entry bookkeeping where a
  journal entry and all its lines must commit atomically or not at all.
- **Unit of Work pattern** — tracks changes to in-memory objects and flushes them in the
  correct SQL dependency order, preventing partial writes.
- **Core + ORM duality** — service-layer code uses ORM models; heavy reporting aggregations
  can drop to Core SQL expressions without framework overhead.
- **Async support** — `asyncpg` + `AsyncSession` compose naturally with FastAPI's `asyncio`
  request handlers.

**Why Alembic?**

Alembic is the canonical migration tool for SQLAlchemy. It generates versioned, reviewable
migration scripts (`alembic upgrade head`) that can be applied automatically in CI/CD or
inspected by a DBA before production. Schema history is tracked inside the database, preventing
drift between environments.

---

### 3.3 Database — PostgreSQL 16

Accounting data is transactional by nature:

- **ACID compliance** is non-negotiable. A credit and its paired debit must both commit or both
  roll back — no partial journal entries.
- **Row-level locking** prevents race conditions when two users post to the same account
  simultaneously.
- **`GENERATED ALWAYS AS` computed columns** support materialized running balances.
- **`jsonb`** provides flexible metadata on transactions without schema migrations.
- **`pgaudit` extension** provides an immutable audit trail required for accounting software
  compliance.
- **Full-text search** indexes transaction notes, vendor names, and line-item descriptions.
- **MVCC** means reads never block writes — important for reporting queries running alongside
  real-time book updates.

**Excluded:**

- **SQLite** — no concurrent writes; unsuitable for multi-user production.
- **MySQL / MariaDB** — weaker transactional semantics for complex multi-table operations;
  missing PostgreSQL extensions used for audit trails and generated columns.

---

### 3.4 Background Jobs — RQ / Arq

Long-running or deferrable work must not block HTTP request handlers:

| Use Case                          | Why Async                                         |
|-----------------------------------|---------------------------------------------------|
| Bank-feed import / CSV parse      | Can take seconds to minutes per file              |
| PDF statement / invoice generation| CPU-bound rendering                               |
| Email delivery                    | External I/O; must be retryable on failure        |
| Scheduled report runs             | Cron-triggered, not user-triggered                |
| Recurring journal entries         | Must not block interactive UI sessions            |

**RQ vs Arq — both are viable for MVP:**

- **RQ (Redis Queue)** is battle-tested, ships a web dashboard, and has a dead-simple API
  (`queue.enqueue(fn, *args)`). Ideal when worker code is synchronous.
- **Arq** is async-native, composing naturally with FastAPI's `asyncio` event loop and
  `asyncpg`. Workers share the same async DB sessions as the API, reducing connection-pool
  overhead.

The codebase abstracts enqueueing behind a thin `jobs.enqueue(task, payload)` interface so the
underlying runtime can be swapped without modifying service-layer code.

**Redis** serves as both the job broker and a general-purpose cache (session tokens,
rate-limit counters, presigned-URL short-links). A single Redis instance is sufficient for
MVP; separate cache vs. broker Redis instances can be split at scale.

---

### 3.5 Frontend — React + Vite + Tailwind CSS

**Why React?**

React's component model and ecosystem are the best-understood tools for complex,
data-dense financial UIs: ledger grids, bank-reconciliation workflows, drill-down dashboards.
React Query handles server-state caching; React Hook Form + Zod handles form validation with
strong TypeScript types.

**Why Vite instead of Next.js / Webpack?**

CairnBooks is **API-first**: all data fetches go through the FastAPI backend, so Next.js
server-side rendering and its required Node.js server process add infrastructure complexity
without benefit. Vite delivers:

- Sub-second HMR during development.
- Production bundles via Rollup with ES module tree-shaking.
- No server process in production — the build output is a static asset bundle served directly
  by Caddy.

Production architecture stays simple: Caddy serves `/*` from the static React bundle and
proxies `/api/*` to the FastAPI process. No Node.js runtime in production containers.

**Why Tailwind CSS?**

- Utility-first classes eliminate CSS specificity conflicts common in large applications.
- PurgeCSS integration at build time keeps the production CSS bundle small.
- Consistent spacing and colour tokens enforce visual coherence without a separate
  design-token pipeline.

Unstyled, accessible Radix UI (or Headless UI) primitives provide the behavioural component
layer; Tailwind supplies the visual layer. Because components are owned by the project rather
than a third-party package, every component can be audited for accessibility and legal
requirements — important for financial software.

---

### 3.6 Object Storage — MinIO / S3-compatible

Binary assets are stored outside the relational database:

| Asset Type                        | Notes                                        |
|-----------------------------------|----------------------------------------------|
| Uploaded bank statements          | CSV, OFX, QFX — up to 50 MB per file        |
| Generated PDF invoices / reports  | Immutable after creation                     |
| Company logo images               | Served via CDN-friendly presigned URLs       |
| Transaction attachments           | Receipts, contracts, scanned documents       |

**Why object storage (not the database)?**

Storing blobs in PostgreSQL inflates table sizes, degrades backup times, and prevents
independent scaling of file storage vs. transactional data. Presigned URLs let the React
frontend upload and download directly without routing payloads through the API process.

**Why MinIO for development?**

MinIO is an S3-compatible open-source object store that runs in a single Docker container.
The `boto3` client configured with `endpoint_url=http://minio:9000` works identically against
MinIO (local dev), Wasabi, or AWS S3 (production) — zero code change required. This preserves
the self-hostable requirement: operators who prefer not to use AWS can deploy MinIO or any
other S3-compatible service in their own infrastructure.

---

## 4. Layered Architecture

### 4.1 Layer Map

```
╔══════════════════════════════════════════════════════════════════════╗
║                          External Clients                            ║
║              Browser (React / Vite SPA)  │  Future mobile clients   ║
╚══════════════════════════════════════════╤═══════════════════════════╝
                                           │  HTTPS
╔══════════════════════════════════════════▼═══════════════════════════╗
║                      Reverse Proxy — Caddy 2                         ║
║              TLS termination · rate limiting · gzip                  ║
║      /api/*  →  FastAPI process     /*  →  static React bundle       ║
╚══════════════════════════════════════════╤═══════════════════════════╝
                                           │ /api/*
╔══════════════════════════════════════════▼═══════════════════════════╗
║                   PRESENTATION LAYER  (api/)                         ║
║      FastAPI routers · Pydantic I/O schemas · Auth middleware        ║
║      OpenAPI 3.1 generation · WebSocket upgrade                      ║
╠══════════════════════════════════════════════════════════════════════╣
║                   APPLICATION LAYER  (services/)                     ║
║      Use-case orchestration: PostJournalEntry, CreateInvoice,        ║
║      ReconcileBankFeed, GenerateReport …                             ║
║      Owns transaction boundaries · Enforces authorization            ║
╠══════════════════════════════════════════════════════════════════════╣
║                   DOMAIN LAYER  (domain/)                            ║
║      Double-entry accounting engine · Balance invariants             ║
║      Tax rule engine · Currency conversion                           ║
║      Pure Python — zero I/O, zero framework imports                  ║
╠══════════════════════════════════════════════════════════════════════╣
║                   INFRASTRUCTURE LAYER  (infrastructure/)            ║
║      SQLAlchemy 2 repositories · S3 adapter (boto3)                  ║
║      Redis client · Email adapter · RQ / Arq task definitions        ║
╚═══════════╤═══════════════════════════════════════════╤══════════════╝
            │                                           │
 ╔══════════▼═════════════╗  ╔═════════════╗  ╔════════▼═════════════╗
 ║   PostgreSQL 16        ║  ║   Redis 7   ║  ║  Object Storage      ║
 ║   primary + replica    ║  ║  cache +    ║  ║  MinIO / S3          ║
 ╚════════════════════════╝  ║  broker     ║  ╚══════════════════════╝
                             ╚══════╤══════╝
                                    │
                           ╔════════▼════════╗
                           ║   RQ / Arq      ║
                           ║   Workers       ║
                           ╚═════════════════╝
```

### 4.2 Layer Responsibilities

| Layer | Owns | Must NOT |
|---|---|---|
| **Presentation** (`api/`) | HTTP routing, request/response validation (Pydantic schemas), authentication middleware, OpenAPI generation, WebSocket upgrade | Contain business logic; issue SQL directly; import SQLAlchemy models |
| **Application** (`services/`) | Use-case orchestration, transaction boundaries, authorization checks, job enqueueing | Contain HTTP concepts (status codes, headers); import SQLAlchemy models directly |
| **Domain** (`domain/`) | Accounting rules, double-entry invariants, balance calculations, tax engine, abstract repository interfaces | Perform any I/O; import any framework (FastAPI, SQLAlchemy, boto3, Redis) |
| **Infrastructure** (`infrastructure/`) | Concrete database repositories, S3 adapter, Redis client, email adapter, RQ/Arq task definitions | Contain business logic; call application services |

### 4.3 Dependency Rule

Dependencies flow **inward only**:

```
Presentation  →  Application  →  Domain
Infrastructure  →  Domain   (implements interfaces defined in the Domain layer)
```

The Domain layer defines abstract repository protocols (e.g. `AccountRepository`,
`JournalRepository`) using `typing.Protocol`. The Infrastructure layer provides concrete
SQLAlchemy implementations. The Application layer depends on the protocols, not the
implementations — allowing unit tests to inject in-memory fakes instead of a real database.

This is the **Dependency Inversion Principle** applied at the layer boundary. A corollary:
the Presentation layer may never import from `infrastructure/` directly; it may only call
Application service methods.

### 4.4 Module Layout

```
cairnbooks/
├── api/                    # Presentation layer — FastAPI routers, Pydantic schemas
│   ├── routes/             #   one module per resource group (accounts, journals, …)
│   └── schemas/            #   request / response Pydantic models
│
├── services/               # Application layer — one class per use case
│   ├── journal_service.py
│   ├── invoice_service.py
│   └── reconcile_service.py
│
├── domain/                 # Domain layer — pure business logic
│   ├── accounting/         #   double-entry engine, chart of accounts, balance rules
│   ├── tax/                #   tax rule engine
│   └── interfaces/         #   abstract repository protocols (typing.Protocol)
│
└── infrastructure/         # Infrastructure layer — concrete adapters
    ├── db/                 #   SQLAlchemy 2 models + repository implementations
    ├── storage/            #   S3 / MinIO client (boto3 wrapper)
    ├── cache/              #   Redis client
    └── jobs/               #   RQ / Arq task definitions
```

CI lint rules (e.g. `import-linter`) will flag any import that violates the dependency rule —
for example `api/` → `infrastructure/db/`, or `domain/` → `api/` — to prevent layer leakage
from creeping in over time.

---

## 5. Consequences

### Positive

- **Accounting correctness is structurally enforced.** Domain-layer functions are pure Python
  with no I/O side effects, making them trivially unit-testable without a running database.
- **API-first by design.** The FastAPI auto-generated OpenAPI spec is the single source of
  truth for the client/server contract. The React frontend uses a generated TypeScript SDK —
  no manual type synchronisation between repos.
- **Self-hostable without compromise.** Every runtime dependency (PostgreSQL, Redis, MinIO)
  ships as an open-source Docker image. No vendor lock-in.
- **Independent scalability.** The stateless FastAPI process scales horizontally behind Caddy.
  PostgreSQL read replicas, Redis, and S3 each scale independently. The job-worker fleet
  scales separately from the API fleet.
- **Swap-friendly job queue.** The `jobs.enqueue()` abstraction allows switching between RQ
  and Arq (or migrating in the future) without touching service-layer code.

### Trade-offs

- **More boilerplate than a monolithic Django app.** The layered separation requires interface
  definitions, dependency injection, and more files per feature. This is intentional —
  accounting software's correctness requirements justify the structural overhead.
- **No SSR for the React SPA.** Vite produces a client-side SPA. Future requirements for
  SEO-optimised public-facing pages (marketing, help centre) would need a separate static site
  or a thin SSR layer.
- **Redis as a single point of failure in MVP.** One Redis instance serves as both job broker
  and cache. A Redis failure disrupts background jobs and rate-limiting simultaneously. Redis
  Sentinel or a managed Redis service should be evaluated before general availability.

---

## 6. Alternatives Considered

| Alternative                         | Reason Rejected                                                                          |
|-------------------------------------|------------------------------------------------------------------------------------------|
| **Django + DRF**                    | Forces Django ORM; admin UI duplicates work; weaker async story for WebSockets           |
| **Node.js / TypeScript backend**    | `decimal.js` is more error-prone than Python `Decimal`; fewer mature accounting libraries |
| **Next.js (instead of Vite)**       | Requires a Node.js server process in production; SSR not needed for an authenticated SPA  |
| **Webpack (instead of Vite)**       | Slower HMR; more complex config; Vite is the community standard for new React projects   |
| **Celery (instead of RQ / Arq)**   | Heavier dependency; pickle-based serialisation is a security concern; RQ/Arq sufficient for MVP task volume |
| **MySQL / MariaDB**                 | Weaker transactional semantics; missing `pgaudit` and generated-column support           |
| **MongoDB**                         | Non-relational; cannot enforce double-entry referential integrity at the database layer   |
| **AWS S3 as a hard dependency**     | Violates self-hostable requirement; MinIO provides an identical API locally               |
| **Local filesystem for blobs**      | Not portable across horizontal replicas; no presigned-URL capability                     |

---

*This ADR is the authoritative reference for the CairnBooks MVP stack. Changes to any listed
technology require a superseding ADR approved by the Architecture Team.*
