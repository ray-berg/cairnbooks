# CairnBooks

Open-source, double-entry accounting platform for small businesses.

## Overview

CairnBooks is an API-first, accounting-correct bookkeeping system built with:

- **Backend**: Python / FastAPI
- **Frontend**: React (Vite)
- **Database**: PostgreSQL (double-entry ledger)
- **Infrastructure**: Docker Compose, deployable on Proxmox LXC

## MVP Scope

The MVP delivers the 24-item scope defined in the project description, including:

- Chart of Accounts management
- Double-entry Journal Entries
- General Ledger
- Trial Balance, P&L, Balance Sheet reports
- Multi-user authentication (JWT)
- RESTful API with OpenAPI docs

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) ≥ 24 with the Compose plugin

### Running the full stack

```bash
make up
```

| Service  | URL                              | Notes              |
|----------|----------------------------------|--------------------|
| API      | http://localhost:8000            | FastAPI + Swagger  |
| Frontend | http://localhost:5173            | React (nginx)      |
| MinIO    | http://localhost:9001            | S3 console         |
| Postgres | `localhost:5432`                 | DB: `cairnbooks`   |
| Redis    | `localhost:6379`                 |                    |

Other useful Make targets:

```bash
make logs    # stream logs from all services
make ps      # show container status / health
make down    # stop services (volumes kept)
make clean   # stop + remove volumes (destructive)
```

Default credentials (dev only):

| Service  | User / Access Key | Password / Secret Key |
|----------|-------------------|-----------------------|
| Postgres | `cairnbooks`      | `cairnbooks`          |
| MinIO    | `cairnbooks`      | `cairnbooks_secret`   |

### Local development (without Docker)

#### Backend

```bash
cd backend
pip install -e ".[dev]"
pytest
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Project Structure

```
CairnBooks/
├── backend/          # FastAPI application
│   ├── app/          # Application source
│   ├── tests/        # Pytest test suite
│   └── pyproject.toml
├── frontend/         # Vite + React application
│   ├── src/          # Application source
│   └── package.json
├── .github/
│   └── workflows/
│       └── ci.yml    # GitHub Actions CI
└── docker-compose.yml
```

## License

MIT — see [LICENSE](LICENSE)
