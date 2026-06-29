# 0026. Staging API Deployment

## Status

Accepted

## Context

StudyBot now has a production-shaped backend foundation: Docker packaging,
PostgreSQL support, Alembic migrations, readiness checks, and CI coverage. The
next portfolio milestone needs a public API environment that reviewers can
inspect without requiring local setup.

## Decision

Deploy a staging FastAPI API as a Docker web service backed by managed
PostgreSQL. Use Render Blueprints to describe the service and database in
`render.yaml`.

The staging deployment will run:

- the existing production Docker image
- `python -m alembic upgrade head` before each deploy
- `/ready` as the deploy health check
- deterministic fake LLM and embedding providers
- production settings validation through `ENVIRONMENT=production`

A dependency-free smoke-test script will verify the deployed API by exercising
the core learning flow against the live URL.

## Consequences

The staging API demonstrates real deployment engineering without introducing AI
provider cost or secret management into the first public environment. It also
keeps deployment drift low because the same Dockerfile, migrations, and health
checks are used locally, in CI, and in staging.

The public staging URL must use explicit HTTPS CORS origins. If Render assigns a
different service URL than the blueprint name, the `CORS_ORIGINS` environment
variable must be updated after resource creation.

Real Groq and OpenAI providers remain a later upgrade. They can be enabled by
changing environment variables and adding provider secrets after the staging
container, database, and migration flow are proven stable.
