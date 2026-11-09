# Staging API Deployment on Render

StudyBot staging runs the production API container against managed PostgreSQL
with deterministic fake AI providers. This keeps the first public deployment
repeatable and inexpensive while still exercising the real production boundaries:
Docker, Alembic migrations, connection pooling, liveness, readiness, and
persistent data.

## Render Blueprint

The repository includes `render.yaml` with:

- one Docker web service: `studybot-api-staging`
- one managed PostgreSQL database: `studybot-postgres-staging`
- `/ready` as the health check path
- `python -m alembic upgrade head` as the pre-deploy migration command
- fake LLM and embedding providers for deterministic demos

Create the Render blueprint from the GitHub repository and review the generated
resources before applying it. Confirm the current Render plan and pricing in the
dashboard before creating paid infrastructure.

## Required Environment

The blueprint sets the deployment defaults:

```text
ENVIRONMENT=production
DATABASE_URL=<managed PostgreSQL connection string>
LLM_PROVIDER=fake
EMBEDDING_PROVIDER=fake
CORS_ORIGINS=https://studybot-api-staging.onrender.com
```

If Render assigns a different public service URL, update `CORS_ORIGINS` to the
actual HTTPS origin. Production validation rejects SQLite, wildcard CORS origins,
localhost CORS origins, unsupported providers, and real providers without their
API keys.

## Deployment Checks

After the first deploy completes, open:

```text
https://studybot-api-staging.onrender.com/health
https://studybot-api-staging.onrender.com/ready
https://studybot-api-staging.onrender.com/docs
```

Expected responses:

- `/health` returns `{"status":"ok", ...}`
- `/ready` returns `{"status":"ready","database":"available"}`
- `/docs` loads the FastAPI OpenAPI UI

The automated smoke runner now targets only the current canonical Vercel staging
URL and local development servers. See [automated staging smoke checks](staging-smoke.md).
For a Render deployment, check the health/readiness URLs above and perform the
learning flow manually; the runner intentionally refuses other remote origins.

Apply migration `20261002_0008` before running this version. Existing accounts
remain locked until an operator sets their passwords with
`python scripts/manage_account.py --email <email> --set-password`. Public
registration never claims existing users or grants admin roles. Use HTTPS and
gateway request limits on `/auth/register`, `/users`, and `/auth/login` before
accepting real users. The frontend's HTTPS origin must be included in `CORS_ORIGINS`.

## Provider Upgrade Path

Keep staging on fake providers until the API deployment is stable. To demo real
AI behavior later, set:

```text
LLM_PROVIDER=groq
GROQ_API_KEY=<secret>
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=<secret>
```

Provider secrets must be stored in Render environment variables, not committed to
the repository.
