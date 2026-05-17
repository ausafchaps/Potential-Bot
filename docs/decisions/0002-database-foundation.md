# 0002 Database Foundation

## Status

Accepted

## Context

StudyBot needs persistent records before document ingestion can be useful. The
first data model should support users, course workspaces, uploaded documents, and
document chunks while staying ready for PostgreSQL and pgvector later.

## Decision

Use SQLAlchemy models with Alembic migrations and UUID primary keys.

The first database module includes:

- `User`
- `Course`
- `Document`
- `DocumentChunk`
- shared timestamp and UUID model mixins
- Alembic configuration driven by app settings
- a controlled `DocumentStatus` enum

SQLite remains the local development database for now. The models use SQLAlchemy
types and relationships that can move to PostgreSQL without changing the domain
model.

## Consequences

This gives document ingestion a stable persistence layer. UUID ids are better for
future public APIs and distributed systems, but they are less compact than integer
ids in local SQLite.

