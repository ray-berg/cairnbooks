# CairnBooks — Architecture Proposal

> Status: **Proposal** | Date: 2026-06-05 | Author: Architecture Team

---

## 1. Purpose and Scope

CairnBooks is an open-source, cloud-ready accounting and business-finance platform targeting small-to-medium businesses. It competes directly with QuickBooks Online, Xero, FreshBooks, Wave, Zoho Books, and Sage Accounting.

This document selects the full technology stack, explains the rationale for each choice, defines the system layering, and establishes architectural invariants that all contributors must respect.

---

## 2. Selected Stack at a Glance

| Concern | Choice | Version |
|---|---|---|
| Backend language | Python | 3.12+ |
| Backend framework | FastAPI | 0.115+ |
| Frontend framework | Next.js (App Router) | 15+ |
| Frontend language | TypeScript | 5.x |
| UI component/style | Tailwind CSS + shadcn/ui | latest |
| Relational database | PostgreSQL | 16+ |
| ORM | SQLAlchemy 2.0 + Alembic | 2.x |
| Background jobs | Celery + Redis (broker) | 5.x |
| Caching / pub-sub | Redis | 7.x |
| Object storage | S3-compatible (Wasabi / AWS S3 / MinIO) | — |
| Auth | JWT (access + refresh) via `python-jose` | — |
| Container runtime | Docker + Docker Compose (dev) | — |
| Reverse proxy | Caddy | 2.x |

---

## 3. Rationale

### 3.1 Backend — Python 3.12 + FastAPI

**Why Python?**

Accounting correctness hinges on exact decimal arithmetic. Python's `decimal.Decimal` type with configurable precision is the standard for financial calculation in open-source projects (GnuCash, Beancount, Ledger-CLI ecosystems). The language has first-class support for the numeric and business-logic work CairnBooks demands.

**Why FastAPI over Django REST Framework or Flask?**

| Criterion | FastAPI | Django REST | Flask |
|---|---|---|---|
| Async-first | Yes (`asyncio`) | No (optional) | No |
| Automatic OpenAPI docs | Yes (Swagger + Redoc) | Plugin needed | Plugin needed |
| Type-safety (Pydantic) | Built-in | Third-party | Third-party |
| Speed (req/s) | ~2× DRF | baseline | ~1.5× DRF |
| Maturity | High | Very High | High |

FastAPI's Pydantic v2 validation layer means every API request and response is schema-validated in one place, producing reliable OpenAPI specs that drive the auto-generated TypeScript client used by the frontend.

Django brings an ORM we would not use (we use SQLAlchemy for explicit control over transactions) and an admin UI that would duplicate work. Flask lacks the async primitives we need for WebSocket support (real-time dashboard updates, collaborative multi-user session awareness).

---

### 3.2 Frontend — Next.js 15 + TypeScript + Tailwind CSS + shadcn/ui

**Why Next.js?**

Accounting UIs have two distinct rendering needs:

- **Server-side rendering (SSR)** for authenticated pages (dashboards, ledgers) that must not be cached by CDNs.
- **Static generation (SSG)** for marketing and help pages.

Next.js App Router handles both. Route-level code splitting keeps the initial bundle small.

**Why TypeScript?**

CairnBooks handles financial data where silent type coercions (number vs. string for monetary amounts, `null` vs. `0` for balances) cause real customer harm. TypeScript eliminates entire classes of these bugs at compile time.

**Why Tailwind CSS + shadcn/ui?**

shadcn/ui provides accessible, un-opinionated Radix UI primitives with Tailwind styling. Because components are copied into the project (not installed as a black-box library), the team can audit and adjust every component — critical for a financial UI with accessibility and legal requirements.

---

### 3.3 Relational Database — PostgreSQL 16

Accounting data is transactional by nature:

- Double-entry bookkeeping requires **atomic, consistent journal entries**. A credit and its paired debit must both commit or both roll back.
- **Row-level locking** prevents race conditions when two users post to the same account concurrently.
- **ACID** compliance is non-negotiable.

PostgreSQL 16 additionally provides:

- `GENERATED ALWAYS AS` computed columns for running balances.
- `jsonb` for flexible metadata on transactions without schema migrations.
- Excellent full-text search for transaction notes and vendor names.
- `pg_audit` extension for immutable audit trails (compliance requirement for accounting software).

SQLite is excluded (no concurrent writes). MySQL/MariaDB is excluded (weaker transactional semantics for complex multi-table operations).

---

### 3.4 ORM — SQLAlchemy 2.0 + Alembic

SQLAlchemy 2.0's **unit-of-work** pattern maps naturally onto the double-entry bookkeeping model:

- A `JournalEntry` aggregate is assembled in memory (debit lines + credit lines + metadata).
- `session.add(entry)` and `session.commit()` flush the entire entry atomically.
- Alembic handles schema migrations with version-controlled, reviewable migration scripts.

Django ORM is excluded because it lacks `session`-level transaction control and explicit locking primitives at the granularity we need.

---

### 3.5 Background Jobs — Celery + Redis

The following operations must not block the request-response cycle:

- **Recurring invoice generation** (scheduled, cron-like)
- **PDF/XLSX report rendering**
- **Email and notification dispatch**
- **Bank feed import and reconciliation**
- **Tax calculation runs over large datasets**

Celery with Redis as broker satisfies all of these. Redis is already in the stack as a cache, so there is no additional infrastructure dependency. Celery Beat handles periodic schedules. Tasks are idempotent by design and carry a task-id for deduplication.

**Why not Temporal or Airflow?** Both are appropriate for complex workflows but carry significant operational overhead. Celery's simplicity matches the team size and near-term requirements; migration to Temporal can be done per-workflow later if needed.

---

### 3.6 Object Storage — S3-Compatible (Wasabi / AWS S3 / MinIO)

The following artifacts must be stored outside the relational database:

- Uploaded receipts and expense documents (JPEG, PDF)
- Generated invoice PDFs
- CSV/XLSX export files
- Company logos and branding assets

Using S3-compatible object storage means:

- **Self-hosters** can run MinIO.
- **Cloud deployments** can use AWS S3 or Wasabi (lower egress cost than S3, GDPR-friendly US-East-1 and EU-Central-1 regions).
- The application code uses `boto3` with the `endpoint_url` parameter, making the backend provider-agnostic.

Files are **never served directly from the application server**. Pre-signed URLs are issued by the backend; the client fetches objects directly from the storage endpoint.

---

### 3.7 Auth — JWT with Refresh Tokens

| Choice | Rationale |
|---|---|
| Short-lived access token (15 min) | Limits blast radius of a leaked token |
| Long-lived refresh token (7 days, rotated) | Balance between UX and security |
| Refresh token stored in `HttpOnly` cookie | Not accessible to JavaScript; mitigates XSS |
| Access token in memory (not localStorage) | Mitigates XSS token theft |
| Role-based access (RBAC) | Owner / Accountant / View-only roles |

OAuth2 social login (Google, Microsoft) is supported via `python-social-auth` as an optional layer on top of the same token infrastructure.

---

## 4. System Layering Diagram

```
╔═══════════════════════════════════════════════════════════════╗
║                      External Clients                         ║
║         Browser (Next.js SPA/SSR) │ Mobile (future)          ║
╚═══════════════════════════════════╤═══════════════════════════╝
                                    │ HTTPS  /  WSS
╔═══════════════════════════════════▼═══════════════════════════╗
║                 Reverse Proxy — Caddy 2                       ║
║          TLS termination, rate limiting, gzip                 ║
╚═══════════════════════════════════╤═══════════════════════════╝
                                    │
          ┌─────────────────────────┴─────────────────────────┐
          │                                                   │
╔═════════▼═════════╗                             ╔═══════════▼═════════╗
║  API Process      ║                             ║ Static Assets / CDN ║
║  FastAPI + Uvicorn║                             ║ (Next.js build out) ║
║  (multiple workers║                             ╚═════════════════════╝
║   via Gunicorn)   ║
╠═══════════════════╣
║  Presentation     ║  ← Route handlers, request validation (Pydantic)
║  Layer            ║    response serialisation, auth middleware
╠═══════════════════╣
║  Application      ║  ← Use-case orchestration (e.g. PostJournalEntry,
║  Layer            ║    CreateInvoice, ReconcileBankFeed)
║  (Services)       ║    No I/O here — pure orchestration
╠═══════════════════╣
║  Domain Layer     ║  ← Core accounting rules, double-entry invariants,
║                   ║    tax engine, currency conversion. No framework
║                   ║    dependencies. Unit-testable in isolation.
╠═══════════════════╣
║  Infrastructure   ║  ← SQLAlchemy 2.0 repositories, S3 client,
║  Layer            ║    email adapter, Redis client, Celery tasks
╚═════════╤═════════╝
          │
    ┌─────┴──────────────────────────────────────────┐
    │                                                │
╔═══▼══════════╗    ╔══════════════╗    ╔════════════▼═══════╗
║ PostgreSQL 16 ║    ║    Redis 7   ║    ║  Object Storage    ║
║ (primary +    ║    ║ cache/broker ║    ║  S3-compatible     ║
║  read replica)║    ╚══════╤═══════╝    ║  (Wasabi/S3/MinIO) ║
╚══════════════╝           │            ╚════════════════════╝
                    ╔══════▼═══════╗
                    ║ Celery Workers║
                    ║ (background   ║
                    ║  jobs)        ║
                    ╚══════════════╝
```

### Layer Responsibilities

| Layer | Owns | Must NOT |
|---|---|---|
| **Presentation** | HTTP routing, auth middleware, Pydantic I/O schemas, rate limiting | Contain business logic or touch DB directly |
| **Application / Services** | Use-case orchestration, transaction boundaries, event emission | Know about HTTP, SQL syntax, or storage URLs |
| **Domain** | Accounting rules, entity models, domain events | Import any framework or I/O library |
| **Infrastructure** | DB sessions, S3 client, email sender, Celery task definitions | Contain business rules |

---

## 5. Accounting-Specific Invariants

The following invariants are enforced at the **Domain layer** and tested exhaustively:

1. **Double-entry balance**: Every `JournalEntry` must have `sum(debits) == sum(credits)` before it can be persisted. A `JournalEntryImbalanceError` is raised otherwise.

2. **Immutable posted entries**: Once a `JournalEntry` is marked `posted`, its lines may never be mutated. Corrections require a reversing entry.

3. **Monetary precision**: All monetary amounts are stored as `NUMERIC(20, 6)` in PostgreSQL and handled as `decimal.Decimal` in Python. Floating-point types (`float`) are prohibited for any monetary field — enforced via Pydantic validators and SQLAlchemy column type constraints.

4. **Multi-currency**: Amounts are always stored with their `currency_code` (ISO 4217). Conversion to the company's base currency is recorded as a separate field at the time of posting; historic rates are never retroactively changed.

5. **Audit trail**: All mutations to `Account`, `JournalEntry`, and `Invoice` records append to an append-only `AuditLog` table via SQLAlchemy events. Rows in `AuditLog` have no `UPDATE` or `DELETE` permissions at the database role level.

6. **Fiscal period lock**: Transactions cannot be posted to a `FiscalPeriod` with `status=CLOSED`. The application layer checks period status before delegating to the domain.

---

## 6. Multi-Tenancy Architecture

CairnBooks enforces strict **tenant isolation** at every layer of the stack. An `Organization` record is the root tenant entity; all other data is owned by exactly one `Organization`. Tenants must never be able to read, write, or even detect the existence of another tenant's data.

### 6.1 Invariant Statement

> **All queries, mutations, background jobs, and stored objects are scoped to a single `organization_id`. Cross-tenant access — even by privileged application code — is prohibited except in a dedicated superadmin context.**

### 6.2 Database Layer — PostgreSQL Row-Level Security

Every business table carries a non-nullable `organization_id UUID` column. PostgreSQL **Row-Level Security (RLS)** policies are enabled on all such tables:

```sql
-- Applied to every tenant-scoped table:
ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON journal_entries
    USING (organization_id = current_setting('app.current_organization_id')::uuid);
```

The application role (`cairnbooks_app`) has no `BYPASSRLS` privilege. A misconfigured query that forgets to set the `app.current_organization_id` session variable will return zero rows, not another tenant's data.

### 6.3 ORM Layer — Tenant-Scoped Sessions

A `TenantSession` wrapper is used throughout the application. It sets the PostgreSQL session variable before executing any statement:

```python
class TenantSession(AsyncSession):
    """Every database session carries the current tenant context."""

    async def execute(self, statement, *args, **kwargs):
        await super().execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true)"),
            {"org_id": str(self._tenant_id)},
        )
        return await super().execute(statement, *args, **kwargs)
```

The `organization_id` is extracted from the validated JWT at request entry and stored in a `contextvars.ContextVar`. The `TenantSession` reads this context variable; no downstream code needs to pass the tenant explicitly.

### 6.4 API Layer — Tenant Extraction Middleware

```python
async def get_current_organization(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session),
) -> Organization:
    payload = verify_jwt(token)          # raises 401 on invalid/expired
    org_id = payload["organization_id"]  # claim set at login
    org = await db.get(Organization, org_id)
    if org is None or not org.is_active:
        raise HTTPException(status_code=403)
    set_tenant_context(org_id)           # sets contextvars.ContextVar
    return org
```

All routes that touch tenant data include `org: Organization = Depends(get_current_organization)`. Routes that exist outside tenant context (login, signup, superadmin) are explicitly excluded.

### 6.5 Background Jobs — Tenant Context in Celery

Every Celery task signature carries `organization_id` as a mandatory keyword argument. The shared task base class restores tenant context at task start:

```python
class TenantTask(celery.Task):
    def __call__(self, *args, **kwargs):
        set_tenant_context(kwargs["organization_id"])
        return super().__call__(*args, **kwargs)
```

Tasks that operate across all tenants (e.g., platform-wide health checks) run under a separate `system` context with explicit superadmin privileges, never under a tenant context.

### 6.6 Object Storage — Tenant-Scoped Prefixes

All S3/MinIO objects are stored under a tenant-namespaced path:

```
s3://<bucket>/orgs/<organization_id>/receipts/<entry_id>/<uuid>.<ext>
s3://<bucket>/orgs/<organization_id>/invoices/<invoice_id>.pdf
s3://<bucket>/orgs/<organization_id>/exports/<timestamp>.csv
```

Presigned URLs are generated by the backend only after validating that the requested `organization_id` matches the authenticated tenant. The frontend never receives AWS credentials.

### 6.7 Superadmin Access

A superadmin role exists for platform operators (support, database maintenance). Superadmin sessions:

- Do **not** set a tenant context — they use a separate `superadmin` PostgreSQL role with `BYPASSRLS`.
- Are accessible only from an IP allowlist.
- Generate an audit log entry for every action, tagged `actor_type = 'superadmin'`.
- Are separated on a `/admin/` router prefix with its own JWT audience (`aud: cairnbooks-admin`).

---

## 7. Data Model Sketch (Core Entities)

```
Organization ──< FiscalYear ──< FiscalPeriod
     │
     ├──< Account (Chart of Accounts)
     │         AccountType: ASSET | LIABILITY | EQUITY | REVENUE | EXPENSE
     │
     ├──< JournalEntry
     │         status: DRAFT | POSTED | REVERSED
     │         ├──< JournalLine (account_id, debit, credit, currency)
     │         └──< AuditLog (append-only)
     │
     ├──< Contact (Customer | Vendor)
     │         ├──< Invoice (AR)
     │         └──< Bill (AP)
     │
     ├──< BankAccount
     │         └──< BankTransaction (imported)
     │
     └──< File (S3 key, mime_type, size)
               linked to: JournalEntry | Invoice | Bill | BankTransaction
```

---

## 8. API Design Conventions (API-First)

CairnBooks is **API-first**: the HTTP API is the canonical interface. The Next.js frontend, mobile apps, and third-party integrations are all equal consumers of the same API. No server-rendered HTML is produced by the backend; no frontend has privileged DB access.

**Invariant**: Any feature that cannot be expressed as an API endpoint does not ship.

- **REST** for CRUD resources (invoices, accounts, contacts).
- **Action endpoints** (`POST /invoices/{id}/send`, `POST /journal-entries/{id}/post`) for state transitions that have business-logic side-effects.
- **WebSocket** channel (`/ws/org/{org_id}/events`) for real-time dashboard refresh (balance changes, payment received notifications).
- All responses follow `{ data: ..., meta: { pagination? } }` envelope.
- Errors follow RFC 9457 Problem Details (`application/problem+json`).
- API versioning via URL prefix: `/api/v1/`.
- OpenAPI spec generated automatically; TypeScript client generated from spec via `openapi-typescript`.

---

## 9. Deployment Topology

```
┌──────────────────── Production ─────────────────────────────┐
│                                                             │
│  Caddy (reverse proxy, auto-TLS)                            │
│       │                                                     │
│       ├── /api/*  → API containers (FastAPI, ×N)            │
│       └── /*      → Next.js container (SSR)                 │
│                                                             │
│  PostgreSQL (primary + 1 streaming replica)                 │
│  Redis (single node; Sentinel for HA in production)         │
│  Celery workers (×M, auto-scaled by queue depth)            │
│  MinIO or Wasabi bucket (object storage)                    │
│                                                             │
│  All services containerised; docker-compose for local dev,  │
│  Compose profiles for staging/prod separation.              │
└─────────────────────────────────────────────────────────────┘
```

Environment variables are the sole configuration mechanism (12-factor). Secrets are never committed; a `.env.example` file documents all required variables.

---

## 10. Self-Hosting vs. Cloud Considerations

CairnBooks is cloud-ready but designed to run on a single machine for self-hosters:

| Capability | Self-hosted (single VPS) | Cloud (managed) |
|---|---|---|
| Database | PostgreSQL in Docker | AWS RDS / Supabase |
| Object storage | MinIO in Docker | AWS S3 / Wasabi |
| Redis | Redis in Docker | AWS ElastiCache / Upstash |
| TLS | Caddy + Let's Encrypt | Caddy or load balancer |
| Email | SMTP relay (any) | AWS SES / Postmark |

No cloud provider is required. The application code is provider-agnostic.

---

## 11. Decisions Deferred

The following decisions are intentionally deferred until the core platform is stable:

| Decision | Deferred Because |
|---|---|
| Mobile app (React Native) | Requires stable API contract first |
| GraphQL endpoint | REST is sufficient for v1 |
| Multi-tenant SaaS billing (Stripe) | Out of scope for initial OSS release |
| Event sourcing for the ledger | Added complexity; revisit if audit log proves insufficient |
| Read model / CQRS | Premature; add read replicas first |

---

## 12. ADR Index

Architecture Decision Records (ADRs) for each major choice above will live in `docs/adr/`. This proposal supersedes prior informal discussions and serves as the basis for all ADRs.

| # | Title | Status |
|---|---|---|
| ADR-001 | Use Python + FastAPI for backend | Accepted |
| ADR-002 | Use Next.js 15 + TypeScript for frontend | Accepted |
| ADR-003 | Use PostgreSQL as the sole relational store | Accepted |
| ADR-004 | Use SQLAlchemy 2.0 + Alembic for ORM/migrations | Accepted |
| ADR-005 | Use Celery + Redis for background jobs | Accepted |
| ADR-006 | Use S3-compatible object storage | Accepted |
| ADR-007 | Prohibit floating-point types for monetary values | Accepted |
| ADR-008 | Enforce immutable posted journal entries | Accepted |
| ADR-009 | Enforce multi-tenancy via PostgreSQL RLS + tenant-scoped sessions | Accepted |
