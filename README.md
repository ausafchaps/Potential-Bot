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

## Planned Capabilities

- Create course or subject workspaces
- Upload PDFs and text notes
- Parse and chunk documents
- Search uploaded material
- Answer questions with citations
- Generate quizzes and flashcards
- Track helpfulness feedback and usage metrics
- Evaluate retrieval and answer quality

## Current API Surface

Health:

- `GET /health`

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

Questions:

- `POST /courses/{course_id}/questions`
- `GET /courses/{course_id}/questions`
- `GET /questions/{question_id}`

Answer feedback:

- `POST /answers/{answer_id}/feedback`

Answer history:

- `GET /answers/{answer_id}`
- `GET /answers/{answer_id}/citations`
- `GET /answers/{answer_id}/feedback`

Admin:

- `GET /admin/metrics`

The current flow is:

```text
create user
-> create course
-> upload text/PDF document
-> inspect documents/chunks
-> search chunks
-> ask grounded questions with fake LLM answers
-> rate answer helpfulness
-> review answer history
-> inspect admin metrics
-> evaluate retrieval quality
-> optionally generate real Groq answers
```

Retrieval is currently keyword-based. PDF ingestion supports text-based PDFs only;
scanned/image PDFs need a later OCR pipeline. Answers currently use a
deterministic fake LLM provider through a provider interface. Retrieval
evaluation uses a small bundled dataset to measure the current keyword baseline
with hit rate, mean reciprocal rank, and precision at k. Authentication,
embeddings, quizzes, and flashcards are planned but not implemented yet.

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
