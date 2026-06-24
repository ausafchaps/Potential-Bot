# 0025 PostgreSQL Foundation

## Status

Accepted

## Context

StudyBot uses SQLite for local development and deterministic tests. SQLite is not
appropriate for the deployed multi-process API because the database file is tied
to one filesystem and its concurrency behavior differs from the target runtime.

The existing SQLAlchemy models and Alembic migrations already use portable UUID,
enum, timestamp, constraint, and foreign-key definitions.

## Decision

Use PostgreSQL as the production and staging database while retaining SQLite for
fast local development and unit tests.

The module includes:

- the Psycopg 3 SQLAlchemy driver
- normalization of managed-host `postgresql://` URLs to `postgresql+psycopg://`
- bounded connection-pool settings with pre-ping and connection recycling
- a `/ready` database connectivity endpoint separate from `/health`
- a PostgreSQL service and integration flow in GitHub Actions
- a local Docker Compose workflow for PostgreSQL and the API
- migration and model-drift verification against both SQLite and PostgreSQL

## Consequences

The application now has an executable database compatibility gate before a
container can pass CI. Local contributors can continue to use SQLite or run the
complete PostgreSQL stack through Docker Compose.

Managed database provisioning, credentials, backup retention, and production
migration execution remain deployment-environment responsibilities.
