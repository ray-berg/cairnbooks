# Contributing to CairnBooks

Thank you for your interest in contributing! This document covers the essentials to get your first pull request merged smoothly.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Branch Strategy](#branch-strategy)
4. [Development Workflow](#development-workflow)
5. [Coding Standards](#coding-standards)
6. [Testing](#testing)
7. [Submitting a Pull Request](#submitting-a-pull-request)
8. [Reporting Issues](#reporting-issues)

---

## Code of Conduct

All participants are expected to follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) code of conduct. Be kind, inclusive, and constructive.

---

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally: `git clone https://github.com/<your-username>/CairnBooks.git`
3. **Set up** the development environment (see [README.md](README.md) — Getting Started).
4. Create a **feature branch** off `main` (see Branch Strategy below).

---

## Branch Strategy

| Branch prefix | Purpose |
|---|---|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `chore/` | Maintenance, tooling, scaffolding |
| `docs/` | Documentation-only changes |
| `test/` | Test additions or fixes |
| `refactor/` | Refactors with no functional change |

Example: `feat/recurring-invoice-generation`

---

## Development Workflow

```bash
# Install backend dependencies (inside backend/)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Install frontend dependencies (inside frontend/)
cd ../frontend
npm install

# Run the full stack locally
docker compose -f deploy/docker-compose.yml up
```

Run backend tests:

```bash
cd backend
pytest
```

Run frontend type-check and lint:

```bash
cd frontend
npm run type-check
npm run lint
```

---

## Coding Standards

### Backend (Python)

- Format with **Black** (`black .`); line length 88.
- Lint with **Ruff** (`ruff check .`).
- Type-annotate all function signatures; `mypy --strict` must pass.
- **Never** use `float` for monetary values — use `decimal.Decimal` only.
- All database queries must go through a `TenantSession`; never bypass RLS.

### Frontend (TypeScript)

- Lint with **ESLint** (`npm run lint`).
- Format with **Prettier** (`npm run format`).
- No `any` types without an explicit `// eslint-disable` comment explaining why.

---

## Testing

- Backend: **Pytest** with `pytest-asyncio` for async routes. Aim for 80%+ coverage on domain and service layers.
- Frontend: **Vitest** for unit tests; **Playwright** for end-to-end tests.
- All CI checks must pass before a PR is merged (see `.github/workflows/`).

---

## Submitting a Pull Request

1. Ensure all tests and linters pass locally.
2. Write a clear PR title and description explaining **what** changed and **why**.
3. Reference any related issues with `Closes #<issue-number>`.
4. Request a review from at least one maintainer.
5. Address review feedback; the PR can be merged once approved and CI is green.

---

## Reporting Issues

Please use the GitHub Issues tracker. Before opening a new issue:

- Search existing issues to avoid duplicates.
- For **security vulnerabilities**, do **not** open a public issue — email the maintainers directly (see `SECURITY.md` when available).
- For bugs, include: steps to reproduce, expected behaviour, actual behaviour, and your environment (OS, Docker version, etc.).
