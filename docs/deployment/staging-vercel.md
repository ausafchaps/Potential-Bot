# Free staging on Vercel and Neon

Use Vercel's Hobby plan and a separate Neon Free project for personal staging.
The frontend and FastAPI API share one HTTPS origin. Start with fake providers for
deterministic smoke checks. The current staging project has an approved Groq Free
connection for real answers, quizzes, and flashcards; embeddings remain fake.

Import this repository at its root with the FastAPI preset. Select the branch
containing `index.py` and `vercel.json`. The build script in `pyproject.toml`
applies Alembic migrations before deployment. The Vercel entry point mounts only
`frontend/` after all API routes, and Vercel promotes these public assets to its
CDN. A failed migration fails the deployment.

Set these environment variables for the staging project's Production environment
(Vercel's environment name does not make this a real production database):

| Variable | Value |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | Secret Neon pooled PostgreSQL URL, with `sslmode=require` |
| `CORS_ORIGINS` | The project's exact HTTPS URL |
| `LLM_PROVIDER` | `fake` |
| `GROQ_API_KEY` | Production-only Secret when enabling approved Groq access |
| `LLM_MODEL` | `openai/gpt-oss-20b` when using Groq |
| `AI_USER_DAILY_LIMIT` | `20` (default) |
| `AI_USER_MINUTE_LIMIT` | `3` (default) |
| `AI_PROJECT_DAILY_LIMIT` | `100` (default) |
| `AI_PROJECT_MINUTE_LIMIT` | `10` (default) |
| `EMBEDDING_PROVIDER` | `fake` |
| `AUTH_SESSION_HOURS` | `24` |
| `AUTH_CLIENT_IP_SOURCE` | `vercel` (automatic when Vercel provides `VERCEL=1`) |
| `DATABASE_POOL_SIZE` | `1` |
| `DATABASE_MAX_OVERFLOW` | `0` |
| `DATABASE_POOL_TIMEOUT_SECONDS` | `30` |
| `DATABASE_POOL_RECYCLE_SECONDS` | `300` |

Do not expose `DATABASE_URL` to frontend code or commit it. Do not share this
database with unrelated preview deployments: their migration builds would modify
the same schema. Use separate databases for independent previews.

The build applies the authentication rate-limit migration before deployment.
Login defaults to 30 attempts per IP and 10 per normalized email per 15-minute
window; the two signup endpoints share 10 attempts per IP per hour. The counters
live in Neon and are shared by all function instances. Both successful and failed
attempts count. HTTP 429 responses include a wait time and `Retry-After`; database
errors return 503 before password work. Existing sessions and logout are unaffected.
Use the positive `AUTH_LOGIN_*` and `AUTH_SIGNUP_*` settings in `.env.example` to
tune the defaults. Keep automatic system environment variables enabled, or set
`AUTH_CLIENT_IP_SOURCE=vercel` explicitly for this gateway-only deployment.
In Vercel mode, missing or invalid platform IP headers fail closed with 503.

For approved real AI access, set `LLM_PROVIDER=groq`. The build applies migration
`20261005_0010` for shared AI generation counters before serving the new version.
Answers, quizzes, and flashcard sets share per-student and project budgets across
all instances. Daily windows reset at midnight UTC; blocked requests return 429
with `Retry-After`. Provider attempts count even when they fail. Insufficient
evidence and fake-provider results do not count. `/auth/ai-usage` returns only the
signed-in student's usage. Request budgets do not meter tokens, and Groq's own
limits can be exhausted earlier. Counter failures return 503 before generation.

The Review tab requires migration `20261009_0011`, applied automatically during the
main build. Existing flashcards become due immediately; reviews save their next
due times in Neon without using AI allowance. Use separate databases for previews.

Vercel functions accept request bodies up to 4.5 MB, including multipart overhead.
Use small text files and PDFs for staging. Requests have a 60-second maximum in
this configuration. Uploaded text, chunks, and authentication sessions persist in
PostgreSQL; the function filesystem is not used for persistent data.

After deployment, verify `/health`, `/ready`, and the frontend, then run:

```powershell
python scripts/staging_smoke.py --base-url https://YOUR-PROJECT.vercel.app
```

This creates disposable staging data and checks authentication, ingestion,
grounded answers, citations, persistence, and logout. Stay within the free plans'
limits; do not enable paid upgrades. Real provider access needs explicit approval
for secret storage and sending retrieved study material to the chosen provider.

Provider references: [FastAPI](https://vercel.com/docs/frameworks/backend/fastapi),
[Hobby](https://vercel.com/docs/plans/hobby), and
[request limits](https://vercel.com/docs/errors/function_payload_too_large).
