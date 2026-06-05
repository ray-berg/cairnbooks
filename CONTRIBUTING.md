# Contributing to CairnBooks

Thank you for your interest in contributing! This document covers everything you need to get your development environment running, understand our conventions, and get your first pull request merged smoothly.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Prerequisites](#prerequisites)
3. [Getting Started](#getting-started)
4. [Branch Strategy](#branch-strategy)
5. [Development Workflow](#development-workflow)
   - [Full-stack (Docker)](#full-stack-docker)
   - [Backend only](#backend-only)
   - [Frontend only](#frontend-only)
6. [Coding Standards](#coding-standards)
7. [Testing](#testing)
8. [Commit Messages](#commit-messages)
9. [Submitting a Pull Request](#submitting-a-pull-request)
10. [Architecture Decision Records](#architecture-decision-records)
11. [CI / CD](#ci--cd)
12. [Reporting Issues](#reporting-issues)
13. [Security Vulnerabilities](#security-vulnerabilities)

---

## Code of Conduct

All participants are expected to follow the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) code of conduct. Be kind, inclusive, and constructive. Violations may be reported to the maintainers.

---

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Docker | 24+ | Required for the full-stack dev environment |
| Docker Compose | v2 (plugin) | Ships with Docker Desktop; `docker compose` (no hyphen) |
| Python | 3.12+ | Only needed if running the backend outside Docker |
| Node.js | 20 LTS+ | Only needed if running the frontend outside Docker |
| Git | 2.38+ | |

---

## Getting Started

1. **Fork** the repository on GitHub and **clone** your fork:

   ```bash
   git clone https://github.com/<your-username>/CairnBooks.git
   cd CairnBooks
   ```

2. **Add the upstream remote** so you can pull in future changes:

   ```bash
   git remote add upstream https://github.com/ray-berg/CairnBooks.git
   ```

3. **Copy the environment template** and fill in the values:

   ```bash
   cp deploy/.env.example deploy/.env
   # Open deploy/.env in your editor and update any values marked "change-me"
   ```

   > **Never commit `deploy/.env`** — it is listed in `.gitignore`. The example file (`deploy/.env.example`) is the source of truth for required variables.

4. **Start all services** with Docker Compose:

   ```bash
   docker compose -f deploy/docker-compose.yml up
   ```

   | Service | URL |
   |---|---|
   | Frontend | <http://localhost:3000> |
   | API | <http://localhost:8000/api/v1/> |
   | Swagger UI | <http://localhost:8000/docs> |
   | Redoc | <http://localhost:8000/redoc> |

5. **Create a feature branch** off `main` (see [Branch Strategy](#branch-strategy)).

---

## Branch Strategy

All work happens on short-lived branches. Use the following prefixes:

| Prefix | Purpose | Example |
|---|---|---|
| `feat/` | New features | `feat/recurring-invoice-generation` |
| `fix/` | Bug fixes | `fix/tax-rounding-off-by-one` |
| `chore/` | Maintenance, tooling, scaffolding | `chore/bump-fastapi-to-0116` |
| `docs/` | Documentation-only changes | `docs/add-adr-jwt-refresh` |
| `test/` | Test additions or fixes | `test/cover-tenant-session-rls` |
| `refactor/` | Refactors with no functional change | `refactor/extract-invoice-service` |

Branch directly from `main`; never stack branches unless explicitly coordinating with a maintainer.

---

## Development Workflow

### Full-stack (Docker)

The recommended path — mirrors the production topology most closely.

```bash
# Start (builds images on first run; use --build to rebuild after dependency changes)
docker compose -f deploy/docker-compose.yml up

# Rebuild a specific service, e.g. after changing requirements-dev.txt
docker compose -f deploy/docker-compose.yml up --build backend

# Tear down (removes containers; --volumes also removes named volumes / database data)
docker compose -f deploy/docker-compose.yml down
```

### Backend only

Useful for fast iteration on API logic without starting the full stack. You still need PostgreSQL and Redis running (use `docker compose up db redis`).

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install all dependencies (including dev/test extras)
pip install -r requirements-dev.txt

# Apply database migrations
alembic upgrade head

# Start the API server with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend only

Useful when working on UI components while the API runs separately (Docker or bare-metal).

```bash
cd frontend

# Install dependencies
npm install

# Start the Next.js dev server
npm run dev
```

The dev server proxies `/api/*` requests to `NEXT_PUBLIC_API_URL` defined in `deploy/.env`.

---

## Coding Standards

### Backend (Python)

- **Format** with [Black](https://black.readthedocs.io/) (`black .`); line length 88.
- **Lint** with [Ruff](https://docs.astral.sh/ruff/) (`ruff check .`); zero warnings policy.
- **Type-check** with mypy (`mypy --strict`); all function signatures must be annotated.
- **Monetary values** — always use `decimal.Decimal`. Never use `float` for amounts, rates, or exchange rates.
- **Database access** — all queries must go through a `TenantSession`; bypassing row-level security is a blocking review comment.
- **Audit log** — financial records are append-only once posted; never mutate or delete posted entries.

Run all backend checks in one command:

```bash
cd backend
black --check . && ruff check . && mypy --strict .
```

### Frontend (TypeScript)

- **Lint** with ESLint (`npm run lint`); zero errors/warnings policy.
- **Format** with Prettier (`npm run format`).
- No `any` types. If unavoidable, add an inline `// eslint-disable-next-line @typescript-eslint/no-explicit-any` comment with a short explanation.
- Use the auto-generated TypeScript client (`frontend/src/lib/api/`) for all API calls; do not hand-roll fetch calls against the API.

Run all frontend checks in one command:

```bash
cd frontend
npm run type-check && npm run lint
```

### Documentation

- Markdown files in `docs/` are linted with [markdownlint-cli](https://github.com/igorshubovych/markdownlint-cli) using the rules in `.markdownlint.json` (MD013 line-length and MD033 inline HTML are disabled).
- Architecture Decision Records live in `docs/adr/` (see [Architecture Decision Records](#architecture-decision-records)).

---

## Testing

### Backend

Tests live in `backend/tests/` and are run with [Pytest](https://docs.pytest.org/):

```bash
cd backend
pytest                          # run all tests
pytest -x                       # stop on first failure
pytest --cov=app --cov-report=term-missing   # with coverage
```

- Use `pytest-asyncio` for async route and service tests.
- **Target**: 80%+ line coverage on the `domain/` and `services/` layers.
- Test fixtures must use isolated database transactions that roll back after each test; never share state between tests.

### Frontend

```bash
cd frontend
npm run test          # Vitest unit tests (watch mode)
npm run test:run      # Vitest single run (for CI)
npm run test:e2e      # Playwright end-to-end tests (requires the full stack to be up)
```

- Unit tests live alongside source files as `*.test.ts(x)`.
- End-to-end tests live in `frontend/e2e/`.

### CI gate

All of the following must be green before a PR can be merged:

- `docs-lint` — markdownlint on `docs/architecture.md`
- Backend format, lint, and type checks
- Backend Pytest suite
- Frontend lint and type-check
- Frontend Vitest unit tests

See `.github/workflows/ci.yml` for the full pipeline definition.

---

## Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) spec. Each commit message must have the form:

```
<type>(<scope>): <short summary>

[optional body]

[optional footer(s)]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`

**Scope** (optional): the part of the codebase affected, e.g. `backend`, `frontend`, `auth`, `invoices`, `ci`

**Examples**:

```
feat(invoices): add PDF generation for recurring invoices

fix(auth): refresh token rotation was not invalidating old token

docs(adr): add ADR-003 for multi-currency storage strategy

chore(deps): bump FastAPI to 0.116.0
```

**Rules**:

- Use the imperative mood in the summary line ("add", not "added" or "adds").
- Keep the summary under 72 characters.
- Reference issues in the footer: `Closes #42` or `Refs #17`.
- Breaking changes: add `BREAKING CHANGE:` in the footer, or append `!` after the type: `feat(auth)!: remove legacy session cookie`.

---

## Submitting a Pull Request

1. **Sync with upstream** before opening your PR:

   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Ensure all checks pass locally** (tests, linters, type-checks) — see [Testing](#testing) and [Coding Standards](#coding-standards).

3. **Push your branch** and open a PR against `main` on the upstream repository.

4. **Write a clear PR description**:
   - **What** changed and **why**.
   - Link any related issues with `Closes #<issue-number>`.
   - Note any migration steps, environment variable additions, or breaking changes.

5. **Request a review** from at least one maintainer. Draft PRs are welcome for early feedback.

6. **Address review comments** — prefer small, focused follow-up commits over force-pushing (makes the review history easier to follow). Squashing is done at merge time.

7. **CI must be green** and at least one approving review is required before merge.

> **Tip**: Keep PRs small and focused. A PR that touches a single feature or fixes a single bug is much easier to review than one that refactors half the codebase. If your change is large, talk to a maintainer about splitting it up.

---

## Architecture Decision Records

Significant architecture and design decisions are documented as Architecture Decision Records (ADRs) in `docs/adr/`. If your contribution introduces a meaningful change to the technology stack, data model, security model, or API contract, please include a new ADR.

Use the lightweight format:

```markdown
# ADR-NNN: Title

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-NNN

## Context
Brief description of the problem or decision that needed to be made.

## Decision
What was decided.

## Consequences
Trade-offs, follow-up tasks, or things this decision rules out.
```

Number ADRs sequentially (e.g. `ADR-004`) and name the file `docs/adr/NNN-slug.md`.

---

## CI / CD

The CI pipeline runs on every push and on pull requests targeting `main`. The workflow file is at `.github/workflows/ci.yml`.

Current jobs:

| Job | Trigger | What it checks |
|---|---|---|
| `docs-lint` | Push / PR | `docs/architecture.md` exists, is non-empty, passes markdownlint |

Additional jobs for backend and frontend linting, type-checking, and tests will be added as those layers are built out. Check the workflow file for the current state.

---

## Reporting Issues

Please use the [GitHub Issues tracker](https://github.com/ray-berg/CairnBooks/issues). Before opening a new issue:

- **Search** existing open and closed issues to avoid duplicates.
- **Use the right label** — `bug`, `enhancement`, `question`, `documentation`.

For **bug reports**, include:

- Steps to reproduce (minimal reproducible case preferred).
- Expected behaviour vs. actual behaviour.
- Your environment: OS, Docker version, browser (if frontend), relevant logs.

For **feature requests**, describe the problem you are trying to solve rather than jumping straight to a solution — it helps maintainers understand the use case.

---

## Security Vulnerabilities

**Do not open a public GitHub issue for security vulnerabilities.**

Please report them directly to the maintainers via email. Responsible disclosure gives us time to patch before the issue is made public. We aim to acknowledge reports within 72 hours and provide a fix timeline within 14 days.

(A formal `SECURITY.md` with contact details will be added to the repository shortly.)
