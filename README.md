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
create user
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
Answers currently use a deterministic fake LLM provider through a provider
interface, and grounded answers use hybrid retrieval for evidence. Retrieval
evaluation uses a small bundled dataset to measure the keyword, vector, and
hybrid paths with hit rate, mean reciprocal rank, and precision at k.
Authentication, spaced repetition, flashcard review tracking, and question-level
concept tagging are planned but not implemented yet.

## Frontend Demo

The local frontend demo is a dependency-free static app in `frontend/`. It talks
to the FastAPI backend and covers the main portfolio flow: workspace creation,
document upload, grounded questions with citations, quiz generation and grading,
weak-topic recommendations, flashcard generation, document summaries, and admin
metrics.

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
LLM_MODEL=llama-3.1-8b-instant
```

`LLM_API_KEY` can also be used instead of `GROQ_API_KEY`. Tests do not call real
provider APIs.

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

## Continuous Integration

The GitHub Actions workflow in `.github/workflows/ci.yml` runs on pull requests
and pushes to `main`. It executes Ruff, the full test suite, Alembic migrations and
model-drift detection on SQLite and PostgreSQL, runs a PostgreSQL learning-flow
integration test, then builds the production API image.
