# CairnBooks

> Open-source, cloud-ready accounting and business-finance platform for small-to-medium businesses.

![CairnBooks](cairnText.png)

CairnBooks is a free, self-hostable alternative to QuickBooks Online, Xero, FreshBooks, and Wave. It is built on a modern, API-first stack with strict double-entry bookkeeping invariants, multi-tenant isolation, and full auditability baked in from day one.

---

## Features

- **Double-entry bookkeeping** — every journal entry is balance-checked before persistence
- **Multi-currency** — amounts stored with ISO 4217 currency codes; historic rates are never retroactively changed
- **Multi-tenancy** — row-level security in PostgreSQL; tenants are cryptographically isolated
- **Audit trail** — append-only audit log on all financial records; immutable once posted
- **Recurring invoices & background jobs** — Celery + Redis for PDF generation, email dispatch, bank-feed import
- **API-first** — OpenAPI 3 spec auto-generated; TypeScript client generated from spec
- **Self-hostable** — single `docker compose up` for local dev; runs on a single VPS in production

---

## Technology Stack

| Concern | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI 0.115+ |
| Frontend | Next.js 15 (App Router) + TypeScript 5 |
| UI | Tailwind CSS + shadcn/ui |
| Database | PostgreSQL 16 |
| ORM / Migrations | SQLAlchemy 2.0 + Alembic |
| Background jobs | Celery 5 + Redis 7 |
| Object storage | S3-compatible (Wasabi / AWS S3 / MinIO) |
| Auth | JWT (access + refresh) |
| Reverse proxy | Caddy 2 |
| Container runtime | Docker + Docker Compose |

---

## Repository Layout

```
CairnBooks/
├── backend/        # Python / FastAPI application
│   ├── app/        # Application source (api, services, domain, infra layers)
│   ├── tests/      # Pytest test suite
│   └── alembic/    # Database migration scripts
├── frontend/       # Next.js 15 application
│   ├── src/        # App router pages, components, hooks
│   └── public/     # Static assets
├── docs/           # Architecture docs, ADRs, API guides
│   └── adr/        # Architecture Decision Records
├── deploy/         # Docker Compose files, Caddy config, env templates
└── .github/        # CI/CD workflows
```

---

## Getting Started

> **Prerequisites**: Docker 24+ and Docker Compose v2.

```bash
# 1. Clone the repo
git clone https://github.com/ray-berg/CairnBooks.git
cd CairnBooks

# 2. Copy environment template and fill in values
cp deploy/.env.example deploy/.env

# 3. Start all services (API, frontend, Postgres, Redis)
docker compose -f deploy/docker-compose.yml up
```

The API will be available at `http://localhost:8000/api/v1/` and the frontend at `http://localhost:3000`.

Interactive API docs (Swagger UI) are at `http://localhost:8000/docs`.

---

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, coding standards, and how to open a pull request.

---

## License

CairnBooks is released under the [MIT License](LICENSE).

Copyright (c) 2026 CairnBooks Contributors
