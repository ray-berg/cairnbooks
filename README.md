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

- Docker & Docker Compose
- Node.js 20+
- Python 3.12+

### Running Locally

```bash
docker compose up
```

The API will be available at `http://localhost:8000` and the frontend at `http://localhost:5173`.

### Development

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
