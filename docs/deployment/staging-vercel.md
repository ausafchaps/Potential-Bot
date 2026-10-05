# Free staging on Vercel and Neon

Use Vercel's Hobby plan and a separate Neon Free project for personal staging.
The frontend and FastAPI API share one HTTPS origin. Keep fake AI providers
enabled so smoke checks do not incur AI charges.

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
limits; do not enable paid upgrades or real AI providers for this setup.

Provider references: [FastAPI](https://vercel.com/docs/frameworks/backend/fastapi),
[Hobby](https://vercel.com/docs/plans/hobby), and
[request limits](https://vercel.com/docs/errors/function_payload_too_large).
