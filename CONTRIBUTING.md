# Contributing to CairnBooks

Thank you for your interest in contributing! This document covers everything you need to get started: development environment setup, the branch and release model, and the code-review process.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Development Setup](#development-setup)
   - [Prerequisites](#prerequisites)
   - [Clone the repository](#clone-the-repository)
   - [Backend (FastAPI)](#backend-fastapi)
   - [Frontend (React + TypeScript)](#frontend-react--typescript)
   - [Full-stack with Docker Compose](#full-stack-with-docker-compose)
3. [Branch Model](#branch-model)
4. [Commit Style](#commit-style)
5. [Submitting Changes](#submitting-changes)
   - [Opening an issue first](#opening-an-issue-first)
   - [Pull requests](#pull-requests)
6. [Review Rules](#review-rules)
7. [License](#license)

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
| PostgreSQL client (`psql`) | 16+ | Optional; useful for inspecting the database |

### Clone the repository

```bash
git clone git@github.com:ray-berg/CairnBooks.git
cd CairnBooks
```

---

### Backend (FastAPI)

The API server lives in `backend/`.

```bash
cd backend

# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies (including development extras)
pip install -e ".[dev]"

# 3. Copy the example environment file and fill in values
cp .env.example .env

# 4. Start dependent services (PostgreSQL + Redis) via Docker Compose
docker compose up -d db redis

# 5. Run database migrations
alembic upgrade head

# 6. Start the development server (auto-reloads on file changes)
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000` and the interactive OpenAPI docs at `http://localhost:8000/docs`.

**Running backend tests:**

```bash
# Unit + integration tests
pytest

# With coverage report
pytest --cov=app --cov-report=term-missing
```

**Linting and formatting:**

```bash
ruff check .          # lint
ruff format .         # format
mypy app              # type-check
```

---

### Frontend (React + TypeScript)

The web client lives in `frontend/`.

```bash
cd frontend

# 1. Install Node dependencies
npm install

# 2. Copy the example environment file
cp .env.example .env.local

# 3. Start the development server (Vite, hot-reload)
npm run dev
```

The app will be available at `http://localhost:5173`.

**Running frontend tests:**

```bash
npm test              # Vitest unit tests
npm run test:e2e      # Playwright end-to-end tests (requires a running backend)
```

**Linting and type-checking:**

```bash
npm run lint          # ESLint
npm run typecheck     # TypeScript compiler (tsc --noEmit)
```

---

### Full-stack with Docker Compose

To spin up every service (API, worker, frontend dev server, PostgreSQL, Redis, MinIO) in one command:

```bash
docker compose up --build
```

Services:

| Service | Local URL |
|---|---|
| Frontend | `http://localhost:5173` |
| API | `http://localhost:8000` |
| API docs (OpenAPI) | `http://localhost:8000/docs` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |
| MinIO console | `http://localhost:9001` |

---

## Branch Model

CairnBooks uses a **trunk-based development** model with short-lived feature branches.

### Long-lived branches

| Branch | Purpose |
|---|---|
| `main` | Always deployable. All feature work merges here. Protected — no direct pushes. |

### Short-lived branches

Branch off `main` using one of the following prefixes:

| Prefix | When to use | Example |
|---|---|---|
| `feat/` | New features or user-visible enhancements | `feat/invoice-pdf-export` |
| `fix/` | Bug fixes | `fix/tax-rounding-line-items` |
| `chore/` | Dependency updates, tooling, CI, non-functional changes | `chore/upgrade-sqlalchemy-2.1` |
| `docs/` | Documentation-only changes | `docs/api-authentication-guide` |
| `refactor/` | Code restructuring with no behaviour change | `refactor/extract-money-value-object` |
| `test/` | Adding or fixing tests only | `test/journal-entry-invariant-coverage` |

**Rules:**

- Branch names are lowercase with hyphens, no spaces or underscores.
- Keep branches short-lived — aim to merge within a few days. Long-running branches cause painful merge conflicts.
- Delete the branch after it is merged.
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

- Use the imperative mood in the description ("add", not "added" or "adds").
- Keep the subject line under 72 characters.
- Reference relevant GitHub issues in the footer: `Closes #42` or `Refs #17`.
- Mark breaking changes with `!` after the type and a `BREAKING CHANGE:` footer:
  ```
  feat(api)!: rename /ledger-entries to /journal-entries

  BREAKING CHANGE: clients must update the URL path.
  ```

---

## Submitting Changes

### Opening an issue first

For anything beyond a trivial fix, **open a GitHub issue before writing code**. This lets the team:

- Confirm the change is wanted.
- Agree on scope and approach before you invest time in an implementation.
- Avoid duplicate effort with parallel work.

Label your issue appropriately: `bug`, `enhancement`, `documentation`, `question`.

### Pull requests

1. Create a branch from `main` following the [branch naming rules](#short-lived-branches).
2. Make your changes in focused, reviewable commits.
3. Write or update tests to cover new behaviour.
4. Ensure the full test suite and linters pass locally before pushing.
5. Push your branch and open a pull request against `main`.
6. Fill in the PR template completely:
   - **What** — a concise summary of the change.
   - **Why** — the motivation and context.
   - **How to test** — steps a reviewer can follow to verify the change manually.
   - **Linked issue(s)** — reference the GitHub issue(s) this PR addresses.
7. Keep the PR focused — one logical change per PR. Split large changes into a sequence of smaller PRs when possible.

---

## Review Rules

All code merged to `main` must pass through a pull-request review. The following rules apply to both authors and reviewers.

### For authors

- Self-review your diff before requesting a review. Check for debug code, leftover TODO comments, and obvious typos.
- Respond to every review comment — either make the requested change, or explain why you disagree in a constructive way.
- Mark conversations as resolved only after you have addressed or explicitly deferred the concern.
- Do not force-push after a review has started (unless asked by a reviewer to squash). Force-pushes destroy comment threads.
- If the PR sits without a review for more than two business days, a gentle ping is appropriate.

### For reviewers

- Aim to review open PRs within **two business days**.
- Be specific and constructive. Link to documentation or examples when suggesting alternatives.
- Distinguish between **blocking** feedback (must be fixed before merge) and **non-blocking** feedback (suggestions, nits). Use a prefix:
  - `nit:` — minor style preference, non-blocking.
  - `question:` — seeking clarification, non-blocking until answered.
  - `suggestion:` — alternative approach worth considering, non-blocking.
  - No prefix or `blocking:` — must be resolved before merge.
- Approve only when you are genuinely satisfied with the change. An approval is a statement of accountability.
- Avoid rubber-stamping; if you are not comfortable reviewing a particular area (e.g., database migrations, financial invariant logic), say so and request an additional reviewer.

### Merge criteria

A PR may be merged when **all** of the following are true:

- [ ] At least **one approving review** from a maintainer.
- [ ] All CI checks pass (tests, lint, type-check).
- [ ] All blocking review comments are resolved.
- [ ] The branch is up to date with `main` (rebase, not merge commit).

Maintainers merge using **squash-and-merge** to keep the `main` history linear and readable. The squash commit message must follow the Conventional Commits format.

---

## License

By contributing you agree that your contributions will be licensed under the [MIT License](LICENSE).
