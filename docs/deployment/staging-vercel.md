# Free staging on Vercel and Neon

Use Vercel's Hobby plan and a separate Neon Free project for personal staging.
The frontend and FastAPI API share one HTTPS origin. Keep fake AI providers
enabled so smoke checks do not incur AI charges.

Import this repository at its root with the FastAPI preset. Select the branch
containing `index.py` and `vercel.json`. The build script in `pyproject.toml`
applies Alembic migrations before copying the frontend into `public/` for the CDN.
A failed migration fails the deployment.

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
| `DATABASE_POOL_SIZE` | `1` |
| `DATABASE_MAX_OVERFLOW` | `0` |
| `DATABASE_POOL_TIMEOUT_SECONDS` | `30` |
| `DATABASE_POOL_RECYCLE_SECONDS` | `300` |

Do not expose `DATABASE_URL` to frontend code or commit it. Do not share this
database with unrelated preview deployments: their migration builds would modify
the same schema. Use separate databases for independent previews.

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
