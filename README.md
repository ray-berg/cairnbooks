# CairnBooks

<p align="center">
  <img src="cairnText.png" alt="CairnBooks" width="320">
</p>

> Open-source, double-entry accounting platform for small businesses.
> API-first · accounting-correct · self-hostable · Docker Compose ready.

---

## Table of Contents

1. [What is CairnBooks?](#what-is-cairnbooks)
2. [MVP Feature Set](#mvp-feature-set)
3. [Quickstart](#quickstart)
4. [Service URLs](#service-urls)
5. [Local Development (without Docker)](#local-development-without-docker)
6. [Project Structure](#project-structure)
7. [Architecture](#architecture)
8. [Contributing](#contributing)
9. [License](#license)

---

## What is CairnBooks?

CairnBooks is a fully open-source, double-entry bookkeeping system designed for small
businesses that need accounting correctness without vendor lock-in. Key design principles:

- **Accounting-correct** — every transaction enforces debits = credits at the domain layer,
  before any persistence. `float` is banned; all monetary values use `decimal.Decimal` /
  `NUMERIC(20,6)`.
- **API-first** — every feature is expressed as a versioned HTTP endpoint. The React UI is
  just one API consumer; third-party integrations are first-class citizens.
- **Self-hostable** — runs on a single `docker compose up`. No mandatory cloud services;
  MinIO replaces S3 in local/on-prem deployments.
- **Multi-tenant** — each organisation's books are isolated at the database layer via
  PostgreSQL Row-Level Security and application-level tenant context.

---

## MVP Feature Set

The MVP delivers 24 scope items including:

| Category | Features |
|---|---|
| **Chart of Accounts** | Create, update, deactivate accounts; account type hierarchy |
| **Journal Entries** | Double-entry posting, reversal entries, fiscal period enforcement |
| **General Ledger** | Account history, running balances, drill-down |
| **Financial Reports** | Trial Balance, Profit & Loss, Balance Sheet |
| **Invoicing** | Draft → sent → paid lifecycle, PDF generation |
| **Bank Reconciliation** | Import CSV/OFX statements, match against journal entries |
| **Multi-user Auth** | JWT access + refresh tokens, organisation-scoped roles |
| **File Attachments** | Upload receipts/documents linked to transactions (S3-compatible) |
| **API Docs** | Interactive OpenAPI 3.1 / Swagger UI auto-generated from the backend |

---

## Quickstart

### Prerequisites

| Requirement | Version |
|---|---|
| [Docker Engine](https://docs.docker.com/get-docker/) | ≥ 24 |
| Docker Compose plugin | included with Docker Desktop / Engine |
| `make` | any recent version |

### 1. Clone the repository

```bash
git clone https://github.com/ray-berg/CairnBooks.git
cd CairnBooks
```

### 2. Start all services

```bash
make up
```

This builds images and starts PostgreSQL, Redis, MinIO, the FastAPI backend, and the React
frontend in the background. Wait ~15 seconds for health checks to pass, then visit:

- **API + Swagger UI** → <http://localhost:8000/docs>
- **Frontend** → <http://localhost:5173>
- **MinIO console** → <http://localhost:9001>

### 3. Useful Make targets

```bash
make logs    # stream logs from all services (Ctrl-C to stop)
make ps      # show container status and health
make down    # stop services (volumes are preserved)
make clean   # stop services and remove volumes — destructive!
make build   # rebuild Docker images without starting
```

### Default dev credentials

> ⚠️  These credentials are for local development only. Change them in any shared environment.

| Service | Username / Access Key | Password / Secret Key |
|---|---|---|
| PostgreSQL | `cairnbooks` | `cairnbooks` |
| MinIO | `cairnbooks` | `cairnbooks_secret` |

---

## Service URLs

| Service | URL | Notes |
|---|---|---|
| **Backend API** | <http://localhost:8000> | FastAPI + Uvicorn |
| **Swagger UI** | <http://localhost:8000/docs> | Interactive API explorer |
| **ReDoc** | <http://localhost:8000/redoc> | Alternative API docs |
| **Frontend** | <http://localhost:5173> | React + Vite (nginx in container) |
| **MinIO console** | <http://localhost:9001> | S3-compatible object storage UI |
| **PostgreSQL** | `localhost:5432` | Database: `cairnbooks` |
| **Redis** | `localhost:6379` | Cache + job broker |

---

## Local Development (without Docker)

Running services individually is useful for faster iteration when you only need to change
one layer.

### Backend

Requires Python 3.12+.

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install the package in editable mode with dev extras
pip install -e ".[dev]"

# Copy and edit environment config
cp .env.example .env               # if present; otherwise set vars manually

# Run database migrations
alembic upgrade head

# Start the development server (auto-reload on file change)
uvicorn app.main:app --reload --port 8000
```

Run the test suite:

```bash
pytest
```

Lint and format:

```bash
ruff check . && ruff format --check .
```

### Frontend

Requires Node.js ≥ 18.

```bash
cd frontend

npm install
npm run dev          # Vite dev server with HMR → http://localhost:5173
npm run build        # Production build → dist/
npm run test         # Vitest unit tests
npm run lint         # ESLint
```

---

## Project Structure

```
CairnBooks/
├── backend/                # Python / FastAPI application
│   ├── app/
│   │   ├── main.py         #   FastAPI app factory + startup
│   │   ├── settings.py     #   Pydantic-settings environment config
│   │   ├── db.py           #   SQLAlchemy async engine + session factory
│   │   ├── api/            #   Presentation layer — routers, Pydantic schemas
│   │   ├── services/       #   Application layer — use-case orchestration
│   │   ├── domain/         #   Domain layer — accounting rules (pure Python)
│   │   └── infrastructure/ #   Infrastructure layer — DB repos, S3, Redis, jobs
│   ├── alembic/            #   Database migration scripts
│   ├── tests/              #   Pytest test suite
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/               # React 18 + Vite + TypeScript application
│   ├── src/
│   │   ├── main.tsx        #   App entry point
│   │   ├── App.tsx         #   Root component
│   │   ├── components/     #   Shared UI components
│   │   ├── pages/          #   Route-level page components
│   │   └── api/            #   Generated TypeScript API client
│   ├── Dockerfile
│   └── package.json
│
├── docs/
│   └── architecture/
│       ├── overview.md     #   System layers + data-flow quick reference
│       └── ADR-0001-stack.md  # Technology stack decision record
│
├── docker-compose.yml      # Full dev stack (Postgres, Redis, MinIO, API, UI)
├── Makefile                # Convenience targets: up, down, logs, ps, clean
├── LICENSE                 # MIT
└── README.md               # ← you are here
```

---

## Architecture

CairnBooks uses a strict four-layer architecture that enforces accounting correctness and
multi-tenancy at every level:

```
Browser (React SPA)
    │ HTTPS
Caddy 2 (reverse proxy — TLS, rate-limiting, gzip)
    │ /api/*                    │ /*
FastAPI (Presentation)     Static React bundle
    │
Application Layer (services/)
    │
Domain Layer (domain/) ← pure Python, zero I/O
    │
Infrastructure Layer (infrastructure/)
    │           │              │
PostgreSQL    Redis         MinIO / S3
(ACID data)  (cache/broker) (file blobs)
                │
           RQ / Arq Workers
```

Dependencies flow **inward only** — the Domain layer never imports from FastAPI, SQLAlchemy,
or Redis. This means every accounting rule is testable with zero infrastructure.

For the full layer map, data-flow diagrams, multi-tenancy enforcement table, and
architectural invariants, see **[docs/architecture/overview.md](docs/architecture/overview.md)**.

For the technology stack rationale and ADRs, see
**[docs/architecture/ADR-0001-stack.md](docs/architecture/ADR-0001-stack.md)**.

---

## Contributing

1. Fork the repository and create a feature branch.
2. Follow the coding conventions in the ADR (Python 3.12+, `ruff`, strict Pydantic models).
3. Ensure `pytest` passes and `ruff check .` reports zero errors before opening a PR.
4. Open a pull request against `main`; the CI pipeline will run tests and lint.

Please read the architecture overview before contributing to understand layer boundaries and
the invariants you must not violate.

---

## License

MIT — see [LICENSE](LICENSE).
