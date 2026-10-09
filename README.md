# StudyBot

StudyBot is an auditable AI study assistant for students working with course notes,
PDFs, slides, assignments, and past papers.

The goal is to build a real AI engineering system, not a thin chatbot wrapper. The
system will ingest user documents, retrieve cited evidence, answer grounded
questions, generate quizzes and flashcards, track weak topics, and measure product
quality.

## Current Status

Backend MVP foundations are underway.

Completed modules:

- FastAPI backend foundation
- SQLAlchemy and Alembic database foundation
- core models for users, courses, documents, and document chunks
- plain text document ingestion with deterministic chunking
- user and course API foundation
- keyword retrieval foundation
- text-based PDF ingestion with page metadata
- document management API
- grounded answer orchestrator with fake LLM provider
- answer feedback API
- answer history API
- admin metrics API
- retrieval evaluation foundation
- real LLM provider integration with Groq
- vector retrieval foundation with deterministic fake embeddings
- real embedding provider integration with OpenAI
- hybrid retrieval foundation
- retrieval evaluation comparison across keyword, vector, and hybrid search
- hybrid retrieval for grounded answers
- quiz generation foundation
- quiz attempts and grading
- weak-topic analytics from quiz attempts
- study recommendations from weak topics
- flashcard generation foundation
- local frontend demo
- PostgreSQL production foundation with readiness checks and CI coverage
- staging API deployment blueprint and smoke-test workflow
- password authentication, revocable bearer sessions, course ownership, and admin roles
- shared database-backed login and signup rate limiting
- shared per-user and project AI generation budgets with a visible allowance
- course study library for reopening saved answers, quizzes, scores, and flashcard sets
- persisted flashcard reviews with answer reveal, ratings, and a due-card queue

## Planned Capabilities

- Create course or subject workspaces
- Upload PDFs and text notes
- Parse and chunk documents
- Search uploaded material
- Answer questions with citations
- Generate quizzes and flashcards
- Submit quiz attempts and store scores
- Track helpfulness feedback and usage metrics
- Evaluate retrieval and answer quality

## Current API Surface

Authentication:

- `POST /auth/register` (email, display_name, password; returns user and bearer session)
- `POST /auth/login` (email, password; returns user and bearer session)
- `GET /auth/me`
- `GET /auth/ai-usage` (the signed-in student's remaining AI allowance and reset times)
- `POST /auth/logout` (revokes the current session)

All coursework and private user endpoints require `Authorization: Bearer <access_token>`.
Only the owner can access a course and its resources; `/admin/metrics` requires an
admin account. `POST /users` remains public registration, now requiring a password.
Health and readiness remain public.

Health:

- `GET /health`
- `GET /ready`

Users and courses:

- `POST /users`
- `GET /users/{user_id}`
- `POST /users/{user_id}/courses`
- `GET /users/{user_id}/courses`
- `GET /courses/{course_id}`

Documents:

- `GET /courses/{course_id}/documents`
- `POST /courses/{course_id}/documents/text`
- `POST /courses/{course_id}/documents/pdf`
- `GET /documents/{document_id}`
- `GET /documents/{document_id}/chunks`
- `DELETE /documents/{document_id}`

Retrieval:

- `GET /courses/{course_id}/search?query={query}&limit={limit}`
- `GET /courses/{course_id}/search/hybrid?query={query}&limit={limit}`
- `GET /courses/{course_id}/search/vector?query={query}&limit={limit}`

Questions:

- `POST /courses/{course_id}/questions`
- `GET /courses/{course_id}/questions`
- `GET /questions/{question_id}`

Quizzes:

- `POST /courses/{course_id}/quizzes`
- `GET /courses/{course_id}/quizzes`
- `GET /quizzes/{quiz_id}`
- `POST /quizzes/{quiz_id}/attempts`
- `GET /quizzes/{quiz_id}/attempts`
- `GET /quiz-attempts/{attempt_id}`
- `GET /courses/{course_id}/weak-topics`
- `GET /courses/{course_id}/study-recommendations`

Flashcards:

- `POST /courses/{course_id}/flashcard-sets`
- `GET /courses/{course_id}/flashcard-sets`
- `GET /flashcard-sets/{flashcard_set_id}`

Answer feedback:

- `POST /answers/{answer_id}/feedback`

Answer history:

- `GET /answers/{answer_id}`
- `GET /answers/{answer_id}/citations`
- `GET /answers/{answer_id}/feedback`

Admin:

- `GET /admin/metrics`

Frontend:

- `frontend/index.html`

The current flow is:

```text
register or log in
-> create course
-> upload text/PDF document
-> inspect documents/chunks
-> search chunks
-> semantically search chunks with fake or OpenAI embeddings
-> search chunks with hybrid keyword/vector ranking
-> ask grounded questions with hybrid-retrieved evidence
-> generate multiple-choice quizzes with citations
-> generate cited flashcard sets
-> submit quiz attempts and review scores
-> inspect weak-topic analytics from quiz attempts
-> get study recommendations from weak topics
-> rate answer helpfulness
-> review answer history
-> inspect admin metrics
-> evaluate retrieval quality
-> optionally generate real Groq answers
-> run the local frontend demo
```

Retrieval supports keyword search, vector search with persisted chunk embeddings,
and hybrid search that combines normalized keyword and vector scores. The default
embedding provider is deterministic and local, and OpenAI embeddings can be
enabled through environment settings for a more realistic retrieval demo before
`pgvector`. PDF ingestion supports text-based PDFs only; scanned/image PDFs need
a later OCR pipeline.
Local development defaults to a deterministic fake LLM provider. Staging uses
Groq's `openai/gpt-oss-20b` for real answers, quizzes, and flashcards; grounded
answers use hybrid retrieval for evidence. Retrieval
evaluation uses a small bundled dataset to measure the keyword, vector, and
hybrid paths with hit rate, mean reciprocal rank, and precision at k.
Flashcard reviews use a simple deterministic spaced-repetition schedule.
Question-level concept tagging and more advanced adaptive scheduling remain planned.

## Frontend Demo

The local frontend demo is a dependency-free static app in `frontend/`. It talks
to the FastAPI backend and covers the main portfolio flow: workspace creation,
document upload, grounded questions with citations, quiz generation and grading,
weak-topic recommendations, flashcard generation, document summaries, and admin
metrics for admin accounts. Sign up or sign in, then create or select one of your
courses. New passwords must contain 12-128 characters.

Open **Library** to browse the selected course's saved answers, quizzes, and
flashcard sets, newest first. Filter by type or search question/title/topic text.
Opening an answer restores its text and source citations; opening a quiz lets
you retake it or review past scores and graded answers. Saved work persists across
reloads and sign-ins. Switching courses clears the previous course's views.
Reopening records uses existing authenticated GET APIs and consumes no AI allowance.

Open **Review** to study cards due now in the selected course. New cards are due
immediately. Reveal the answer and citations, then choose Again, Hard, Good, or
Easy. Again schedules 10 minutes; the other ratings start at 1, 3, and 7 days and
extend existing intervals by 1.2, 2, and 3 times (capped at 365 days). Scheduling
uses elapsed time in UTC; the UI displays local due times. Reviewed cards return
when due, and progress survives reloads and sign-ins. Reviews use no AI allowance.
Apply migration `20261009_0011` before serving this version; Vercel applies it during
the main deployment build. This is a simple heuristic, not FSRS or SM-2.

Review APIs:

- `GET /courses/{course_id}/flashcard-review?limit=20` (1–50 cards, counts and next due time)
- `POST /flashcards/{flashcard_id}/reviews` (`rating` and the queue card's `version`)

Only the course owner can read or rate its cards. The version prevents concurrent
or repeated submissions from scheduling a card twice. HTTP 409 refreshes the queue;
storage failures return 503 and leave the UI ready to retry. Progress keeps the
latest rating and total review count, rather than a full review-event history.

Apply the authentication migration before starting the backend:

```powershell
alembic upgrade head
```

Start the backend:

```powershell
uvicorn app.main:app --reload --app-dir backend
```

Serve the frontend:

```powershell
python -m http.server 5173 --directory frontend
```

Open:

```text
http://127.0.0.1:5173
```

## Account Administration

Accounts register as ordinary students. There is no default admin password.
An operator with trusted server/database access can grant admin access:

```powershell
python scripts/manage_account.py --email admin@example.com --admin
```

Users created before authentication remain locked until an operator sets a password:

```powershell
python scripts/manage_account.py --email student@example.com --set-password
```

The command prompts for a password without echoing it and revokes all existing
sessions on password changes. Use `--remove-admin` to remove the role or
`--revoke-sessions` to sign an account out everywhere. Never set credentials using
public registration to claim an existing account. Registration rejects duplicate
emails, including legacy accounts.

Sessions expire after `AUTH_SESSION_HOURS` (default 24). The frontend stores its
session in sessionStorage and clears it on logout, expiry, and API changes.
Login allows 30 attempts per IP and 10 per normalized email in each 15-minute
window. Signup allows 10 attempts per IP per hour, shared by `/auth/register` and
`/users`. Both successful and failed attempts count. Limits use atomic database
counters shared across processes and Vercel instances; throttling returns HTTP 429
with `Retry-After` and a wait time in the message. Existing sessions and logout
continue to work while sign-in is throttled. Storage errors fail closed with 503.
Apply `alembic upgrade head` before running the updated API.

Configure positive `AUTH_LOGIN_IP_LIMIT`, `AUTH_LOGIN_EMAIL_LIMIT`,
`AUTH_LOGIN_WINDOW_SECONDS`, `AUTH_SIGNUP_IP_LIMIT`, and `AUTH_SIGNUP_WINDOW_SECONDS`
values as needed. Windows align to Unix time and can admit a burst on either side
of a boundary. Counters contain SHA-256 bucket keys rather than plaintext emails
or IPs; each auth request removes up to 100 buckets expired more than a day ago.

The default IP source is the ASGI client address. Vercel automatically selects
its platform `x-vercel-forwarded-for` header when the system variable `VERCEL=1`
is present. `AUTH_CLIENT_IP_SOURCE=direct` or `vercel` can override this choice.
Enable `vercel` only behind Vercel's gateway; arbitrary forwarding headers are
ignored in direct mode. Other hosts must configure their ASGI server to trust
only their gateway's proxy addresses. Email verification, self-service password
recovery, and MFA remain follow-up work. Public deployments require HTTPS and
gateway request limits as an additional layer before application/body processing.

## LLM Providers

StudyBot uses a provider interface for answer generation. The default provider is
deterministic and free:

```powershell
LLM_PROVIDER=fake
```

To use Groq for real answers, set:

```powershell
LLM_PROVIDER=groq
GROQ_API_KEY=your-api-key
LLM_MODEL=openai/gpt-oss-20b
```

`LLM_API_KEY` can also be used instead of `GROQ_API_KEY`. Tests do not call real
provider APIs.

Real generations share one allowance across every course, answer, quiz, and
flashcard set. Defaults are 20 attempts per student per UTC day, 3 per minute,
100 for the whole project per UTC day, and 10 per minute. Set positive
`AI_USER_DAILY_LIMIT`, `AI_USER_MINUTE_LIMIT`, `AI_PROJECT_DAILY_LIMIT`, and
`AI_PROJECT_MINUTE_LIMIT` values to tune them. There is no admin exemption.
One quiz or flashcard set counts as one attempt regardless of its item count.
Fake-provider requests and insufficient-evidence results use no allowance.

Reservations are atomic database counters shared across API instances. They
commit before the provider call; failures and timeouts count because the provider
may have performed work. Rejected requests consume no allowance. HTTP 429 returns
`Retry-After` and a readable wait message. Counter storage failures block generation
with 503; reading existing study material and logout remain available. The frontend
shows remaining daily/minute allowance and refreshes it after each generation.
Groq throttling also returns a readable 429 with a safe retry delay.

These are request-count budgets, not token metering. They reduce usage but do not
guarantee staying inside provider token limits, especially for larger requests or
other apps sharing the Groq organization. Provider limits can be reached sooner.
Fixed windows allow bursts around their boundaries. Expired buckets are cleaned
up in bounded batches, and contain no prompts, documents, or plaintext user IDs.
Apply `alembic upgrade head` (including `20261005_0010`) before serving this version.

## Embedding Providers

StudyBot also uses a provider interface for vector retrieval. The default
embedding provider is deterministic and free:

```powershell
EMBEDDING_PROVIDER=fake
```

To use OpenAI embeddings for vector and hybrid retrieval, set:

```powershell
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=your-openai-api-key
EMBEDDING_MODEL=text-embedding-3-small
```

`OPENAI_API_KEY` can also be used instead of `EMBEDDING_API_KEY`. Optional
`EMBEDDING_DIMENSIONS` is supported for models that allow shorter embeddings.
Tests mock the provider and do not call OpenAI.

## Architecture Decisions

Decision records live in `docs/decisions`.

- `0001-backend-foundation.md`
- `0002-database-foundation.md`
- `0003-text-ingestion.md`
- `0004-user-course-api.md`
- `0005-retrieval-foundation.md`
- `0006-pdf-ingestion.md`
- `0007-document-management-api.md`
- `0008-grounded-answer-orchestrator.md`
- `0009-answer-feedback-api.md`
- `0010-answer-history-api.md`
- `0011-admin-metrics-api.md`
- `0012-retrieval-evaluation-foundation.md`
- `0013-real-llm-provider-integration.md`
- `0014-vector-retrieval-foundation.md`
- `0015-hybrid-retrieval-foundation.md`
- `0016-retrieval-eval-comparison.md`
- `0017-hybrid-grounded-answers.md`
- `0018-quiz-generation-foundation.md`
- `0019-quiz-attempts-grading.md`
- `0020-weak-topic-analytics.md`
- `0021-study-recommendations.md`
- `0022-flashcard-generation-foundation.md`
- `0023-openai-embedding-provider.md`
- `0024-frontend-demo.md`
- `0025-postgresql-foundation.md`
- `0026-staging-api-deployment.md`
- `0027-authentication.md`
- `0028-authentication-rate-limiting.md`
- `0029-ai-usage-limits.md`

## Branch Workflow

- `main` contains stable merged work
- feature branches use `feature/<module-name>`
- each module should include tests and docs when architecture changes
- pull requests are merged into `main` after review

## Local Development

Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the API:

```powershell
uvicorn app.main:app --reload --app-dir backend
```

Open the API docs at:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```powershell
pytest
```

Run linting:

```powershell
ruff check .
```

Check the frontend with Node.js 24 (no npm dependencies):

```powershell
node --check frontend/app.js
node --test frontend/tests/*.test.cjs
```

Check Alembic model drift:

```powershell
alembic check
```

## Container Development

Build the production API image:

```powershell
docker build --tag studybot:local .
```

Create the local container database schema:

```powershell
docker volume create studybot-data
docker run --rm --volume studybot-data:/data studybot:local alembic upgrade head
```

Run the API:

```powershell
docker run --rm --name studybot-api --publish 8000:8000 --volume studybot-data:/data studybot:local
```

Verify the deployment at `http://127.0.0.1:8000/health` and open the API docs at
`http://127.0.0.1:8000/docs`.

The container runs as a non-root user and defaults to deterministic fake AI
providers. Pass provider configuration through environment variables at runtime;
do not copy `.env` or API keys into the image. SQLite is suitable for this local
container workflow only. Production configuration rejects SQLite, non-HTTPS CORS
origins, unsupported providers, and real AI providers without their required
credentials. The production deployment will use managed PostgreSQL.

## PostgreSQL Development

Start PostgreSQL and the API together:

```powershell
docker compose up --build
```

The API waits for PostgreSQL, applies Alembic migrations, and starts on
`http://127.0.0.1:8000`. Check application liveness at `/health` and database
readiness at `/ready`.

Stop the services without deleting database data:

```powershell
docker compose down
```

Delete the local PostgreSQL volume only when a clean database is required:

```powershell
docker compose down --volumes
```

Production and staging must provide `DATABASE_URL` as a secret. Managed-host URLs
using `postgresql://` are normalized to Psycopg automatically. Connection pool
size, overflow, timeout, and recycling are configurable with the corresponding
`DATABASE_POOL_*` environment variables documented in `.env.example`.

## Staging Deployment

StudyBot includes a Render Blueprint in `render.yaml` for a staging API service
and managed PostgreSQL database. The staging service runs the production Docker
image, applies Alembic migrations before deploy, uses `/ready` for readiness, and
keeps deterministic fake AI providers enabled.

For free personal staging, Vercel Hobby can host the frontend and API with a
separate Neon Free PostgreSQL project. Setup, environment variables, migrations,
and upload limits are documented in [the Vercel staging guide](docs/deployment/staging-vercel.md).
The Render alternative is documented in `docs/deployment/staging-render.md`.

After deployment, run:

```powershell
python scripts/staging_smoke.py --base-url https://studybot-api-staging.onrender.com
```

The smoke test verifies liveness, database readiness, user and course creation,
authentication, text ingestion, grounded answers, citations, persistence, and logout.

## Continuous Integration

The GitHub Actions workflow in `.github/workflows/ci.yml` runs on pull requests
and pushes to `main`. It executes Ruff, the full test suite, Alembic migrations and
model-drift detection on SQLite and PostgreSQL, runs a PostgreSQL learning-flow
integration test, then builds the production API image.
