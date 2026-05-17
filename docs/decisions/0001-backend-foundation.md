# 0001 Backend Foundation

## Status

Accepted

## Context

StudyBot should be built in small, inspectable modules with clean boundaries,
version control, tests, and documentation from the start.

## Decision

Use a backend-first foundation:

- FastAPI for the API layer
- `pyproject.toml` with pip-compatible project metadata
- SQLAlchemy for the data layer
- SQLite for local development first
- pytest for backend tests
- ruff for linting

The codebase will keep the backend under `backend/app` and tests under
`backend/tests`.

## Consequences

This keeps the first milestone lightweight while preserving a clear path to
PostgreSQL, pgvector, Alembic migrations, document ingestion, retrieval, and
frontend work later.

