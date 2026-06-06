# CairnBooks

> Open-source, cloud-ready double-entry accounting platform for small businesses.

## Development Quick Start

```bash
pip install uv && uv pip install -e ".[dev]" && pytest
```

## Stack

| Concern | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI 0.115+ |
| Database | PostgreSQL 16 |
| ORM / Migrations | SQLAlchemy 2.0 + Alembic |
| Package manager | uv |
| Linter | ruff |
| Tests | pytest |

## Repository Layout

```
CairnBooks/
├── src/cairnbooks/   # Python package (src layout)
├── tests/            # pytest test suite
├── pyproject.toml    # project metadata and tool config
└── .github/          # CI/CD workflows
```

## Getting Started (Docker)

```bash
git clone https://github.com/ray-berg/CairnBooks.git
cd CairnBooks
docker compose up
```

## License

MIT — see [LICENSE](LICENSE).
