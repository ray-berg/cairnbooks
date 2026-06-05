# CairnBooks — Deployment Guide

> **Status:** Skeleton / local-dev only — no application code is wired up yet.
> This document will grow as backend and frontend images are built out.

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| Docker | 24.x |
| Docker Compose (plugin) | v2.x (`docker compose`, not `docker-compose`) |

---

## Quick start (one command)

```bash
# 1. Clone the repository (if you haven't already)
git clone https://github.com/ray-berg/CairnBooks.git
cd CairnBooks

# 2. Create your local environment file
cp deploy/.env.example deploy/.env
#    ^^^ Edit deploy/.env and set real values before continuing.

# 3. Bring up the full stack
docker compose -f deploy/docker-compose.yml up
```

All services start in the foreground. Press `Ctrl-C` to stop them.

To start in detached (background) mode:

```bash
docker compose -f deploy/docker-compose.yml up -d
```

To stop and remove containers (data volume is preserved):

```bash
docker compose -f deploy/docker-compose.yml down
```

To also remove the persistent Postgres volume (⚠ destroys all data):

```bash
docker compose -f deploy/docker-compose.yml down -v
```

---

## Services

| Service | Image | Default port | Purpose |
|---|---|---|---|
| `db` | `postgres:16-alpine` | `5432` | Primary relational database |
| `backend` | `python:3.12-slim` *(placeholder)* | `8000` | FastAPI application |
| `frontend` | `node:20-alpine` *(placeholder)* | `3000` | Next.js 15 application |

### Placeholder services

`backend` and `frontend` currently run simple HTTP servers so the
`docker compose up` command completes successfully and the port mappings can
be verified before application code exists. They will be replaced with proper
`build:` directives pointing at `./backend` and `./frontend` once the
respective Dockerfiles are added.

---

## PostgreSQL healthcheck

The `db` service includes a Docker healthcheck that runs `pg_isready` every
**10 seconds** with a **5-second timeout** and **5 retries** (plus a 10-second
start-up grace period).

```
HEALTHCHECK interval=10s timeout=5s retries=5 start_period=10s
  CMD pg_isready -U <POSTGRES_USER> -d <POSTGRES_DB>
```

All services that require the database (`backend`) use `depends_on` with
`condition: service_healthy`, so they will not start until Postgres is
accepting connections.

---

## Environment variables

All runtime configuration is driven by `deploy/.env` (git-ignored). The
template `deploy/.env.example` documents every supported variable with safe
defaults. Key variables:

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_DB` | `cairnbooks` | Database name |
| `POSTGRES_USER` | `cairnbooks_app` | Database role |
| `POSTGRES_PASSWORD` | `change-me` | **Must be changed in production** |
| `SECRET_KEY` | `change-me-…` | Django-style secret — used for signing |
| `JWT_SECRET_KEY` | `change-me-…` | JWT signing key |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Frontend → API base URL |

> ⚠ Never commit `deploy/.env` to version control. It is listed in `.gitignore`.

---

## Data persistence

Postgres data is stored in a named Docker volume (`postgres_data`). This
volume survives `docker compose down` restarts. It is only removed when you
run `docker compose down -v` explicitly.

---

## Verifying the stack

After `docker compose up`:

```bash
# Postgres is healthy
docker compose -f deploy/docker-compose.yml ps

# Connect to Postgres directly
docker compose -f deploy/docker-compose.yml exec db \
  psql -U cairnbooks_app -d cairnbooks -c "\l"

# Backend placeholder responds
curl http://localhost:8000

# Frontend placeholder responds
curl http://localhost:3000
```

---

## Next steps (TODO — not yet implemented)

- [ ] Add `./backend/Dockerfile` and switch `backend` service to `build: ./backend`
- [ ] Add `./frontend/Dockerfile` and switch `frontend` service to `build: ./frontend`
- [ ] Add `redis` service for Celery broker/result-backend
- [ ] Add `worker` service (Celery) dependent on `redis` and `db`
- [ ] Add `caddy` reverse-proxy service for local HTTPS and path routing
- [ ] Add Alembic migration step (or init container) that runs before `backend`
- [ ] Document staging and production deployment (VPS / cloud target TBD)
