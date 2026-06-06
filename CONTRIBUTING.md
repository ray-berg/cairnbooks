# Contributing to CairnBooks

Thank you for your interest in contributing! This document covers everything you need to get started: development environment setup, running tests, the branch and release model, and the code-review process.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Development Setup](#development-setup)
   - [Prerequisites](#prerequisites)
   - [Clone the repository](#clone-the-repository)
   - [Backend (Python)](#backend-python)
   - [Frontend (Node / React)](#frontend-node--react)
   - [Full-stack with Docker Compose](#full-stack-with-docker-compose)
3. [Running Tests](#running-tests)
   - [Backend tests](#backend-tests)
   - [Frontend tests](#frontend-tests)
4. [Linting and Type-checking](#linting-and-type-checking)
5. [Branch Model](#branch-model)
6. [Commit Style](#commit-style)
7. [Submitting Changes](#submitting-changes)
   - [Opening an issue first](#opening-an-issue-first)
   - [Pull requests](#pull-requests)
8. [Review Rules](#review-rules)
9. [License](#license)

---

## Code of Conduct

Be respectful and constructive. We follow the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

---

## Development Setup

### Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Git | 2.40+ | |
| Python | 3.12+ | Use [pyenv](https://github.com/pyenv/pyenv) to manage versions |
| Node.js | 20 LTS | Use [nvm](https://github.com/nvm-sh/nvm) to manage versions |
| Docker + Docker Compose | 24+ / 2.20+ | Required for the full-stack setup |
| PostgreSQL client (`psql`) | 16+ | Optional — useful for inspecting the database directly |

### Clone the repository

```bash
git clone git@github.com:ray-berg/CairnBooks.git
cd CairnBooks
```

External contributors should **fork** first, then clone their fork:

```bash
# Fork via the GitHub UI, then:
git clone git@github.com:<your-username>/CairnBooks.git
cd CairnBooks
git remote add upstream git@github.com:ray-berg/CairnBooks.git
```

---

### Backend (Python)

The API server lives in `backend/`.

```bash
cd backend

# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install the package with development dependencies
pip install -e ".[dev]"

# 3. Copy the example environment file and fill in the required values
cp .env.example .env

# 4. Start dependent services (PostgreSQL + Redis) via Docker Compose
docker compose up -d db redis

# 5. Apply database migrations
alembic upgrade head

# 6. Start the development server (auto-reloads on file changes)
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`.  
Interactive OpenAPI documentation: `http://localhost:8000/docs`.

---

### Frontend (Node / React)

The web client lives in `frontend/`.

```bash
cd frontend

# 1. Install Node dependencies
npm install

# 2. Copy the example environment file
cp .env.example .env.local

# 3. Start the development server (Vite, hot-module reload)
npm run dev
```

The app is available at `http://localhost:5173`.

---

### Full-stack with Docker Compose

To spin up every service in one command from the repository root:

```bash
docker compose up --build
```

| Service | Local URL |
|---|---|
| Frontend | `http://localhost:5173` |
| API | `http://localhost:8000` |
| OpenAPI docs | `http://localhost:8000/docs` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

---

## Running Tests

All tests must pass before a PR can be merged. Run the full suite locally before pushing.

### Backend tests

```bash
cd backend
source .venv/bin/activate

# Run the full test suite
pytest

# Run with a coverage report
pytest --cov=app --cov-report=term-missing

# Run a specific test file or test
pytest tests/test_journal.py
pytest tests/test_journal.py::test_tax_rounding
```

### Frontend tests

```bash
cd frontend

# Vitest unit and component tests
npm test

# Run tests once (CI mode, no watch)
npm run test:run

# Playwright end-to-end tests (requires a running backend)
npm run test:e2e
```

---

## Linting and Type-checking

Fix all lint and type errors before opening a PR. CI enforces this.

**Backend:**

```bash
cd backend
ruff check .          # lint
ruff format .         # format
mypy app              # type-check
```

**Frontend:**

```bash
cd frontend
npm run lint          # ESLint
npm run typecheck     # TypeScript compiler (tsc --noEmit)
```

---

## Branch Model

CairnBooks uses a **trunk-based development** model with short-lived feature branches.

### Long-lived branches

| Branch | Purpose |
|---|---|
| `main` | Always deployable. All work merges here. Protected — no direct pushes. |

### Short-lived branches

Branch off `main` using one of the following prefixes:

| Prefix | When to use | Example |
|---|---|---|
| `feat/` | New features or user-visible enhancements | `feat/invoice-pdf-export` |
| `fix/` | Bug fixes | `fix/tax-rounding-line-items` |
| `chore/` | Dependency updates, tooling, CI, non-functional changes | `chore/upgrade-sqlalchemy-2-1` |
| `docs/` | Documentation-only changes | `docs/api-authentication-guide` |
| `refactor/` | Code restructuring with no behaviour change | `refactor/extract-money-value-object` |
| `test/` | Adding or fixing tests only | `test/journal-entry-invariant-coverage` |

**Rules:**

- Branch names are lowercase with hyphens, no spaces or underscores.
- Keep branches short-lived — aim to merge within a few days. Long-running branches cause painful merge conflicts.
- Delete your branch after it is merged.
- Never commit directly to `main`. Branch protection enforces this.
- Rebase on `main` before opening a PR to keep history linear:

  ```bash
  git fetch origin
  git rebase origin/main
  ```

---

## Commit Style

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <short description>

[optional body]

[optional footer(s)]
```

**Allowed types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`

**Examples:**

```
feat(invoices): add PDF export endpoint
fix(journal): correct tax rounding on line items
docs: expand development setup guide
chore: upgrade FastAPI to 0.111
test(accounts): add coverage for deactivated-account invariant
```

**Rules:**

- Use the imperative mood ("add", not "added" or "adds").
- Keep the subject line under 72 characters.
- Reference relevant GitHub issues in the footer: `Closes #42` or `Refs #17`.
- Mark breaking changes with `!` after the type and a `BREAKING CHANGE:` footer:

  ```
  feat(api)!: rename /ledger-entries to /journal-entries

  BREAKING CHANGE: clients must update the endpoint path.
  ```

---

## Submitting Changes

### Opening an issue first

For anything beyond a trivial fix, **open a GitHub issue before writing code**. This lets the team:

- Confirm the change is wanted.
- Agree on scope and approach before you invest time in an implementation.
- Avoid duplicate effort with in-progress work.

Label your issue appropriately: `bug`, `enhancement`, `documentation`, `question`.

### Pull requests

1. Create a branch from `main` following the [branch naming rules](#short-lived-branches).
2. Make your changes in focused, reviewable commits.
3. Write or update tests to cover new behaviour.
4. Ensure the full test suite and linters pass locally before pushing.
5. Push your branch and open a pull request against `main`.
6. Fill in the PR template completely:
   - **What** — a concise summary of the change.
   - **Why** — motivation and context.
   - **How to test** — steps a reviewer can follow to verify the change manually.
   - **Linked issue(s)** — reference the GitHub issue(s) this PR addresses.
7. Keep each PR focused on one logical change. Split large changes into a sequence of smaller PRs when possible.

---

## Review Rules

All code merged to `main` must pass through a pull-request review.

### For authors

- Self-review your diff before requesting a review. Remove debug code, stray TODO comments, and obvious typos.
- Respond to every review comment — either make the change, or explain constructively why you disagree.
- Mark conversations resolved only after you have addressed or explicitly deferred the concern.
- Do not force-push after a review has started (unless a reviewer asks for a squash). Force-pushes destroy comment threads.
- If a PR has received no review after two business days, a polite ping in the issue or PR is appropriate.

### For reviewers

- Aim to review open PRs within **two business days**.
- Be specific and constructive. Link to documentation or examples when suggesting alternatives.
- Distinguish blocking feedback from suggestions using a comment prefix:

  | Prefix | Meaning |
  |---|---|
  | `nit:` | Minor style preference — non-blocking |
  | `question:` | Seeking clarification — non-blocking until answered |
  | `suggestion:` | Alternative worth considering — non-blocking |
  | *(none)* or `blocking:` | Must be resolved before merge |

- Approve only when you are genuinely satisfied. An approval is a statement of accountability.
- If you are not comfortable reviewing a specific area (e.g., database migrations, financial invariant logic), say so and request an additional reviewer.

### Merge criteria

A PR may be merged when **all** of the following are true:

- [ ] At least **one approving review** from a maintainer.
- [ ] All CI checks pass (tests, lint, type-check).
- [ ] All blocking review comments are resolved.
- [ ] The branch is up to date with `main` (rebased, not merged).

Maintainers merge using **squash-and-merge** to keep `main` history linear and readable. The squash commit message must follow the Conventional Commits format.

---

## License

By contributing you agree that your contributions will be licensed under the [GNU General Public License v3.0](LICENSE).
