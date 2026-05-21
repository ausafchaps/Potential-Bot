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

- `POST /courses/{course_id}/documents/text`

Retrieval:

- `GET /courses/{course_id}/search?query={query}&limit={limit}`

The current flow is:

```text
create user -> create course -> upload text document -> persist chunks -> search chunks
```

Retrieval is currently keyword-based. Authentication, PDF parsing, embeddings,
grounded answers, quizzes, and flashcards are planned but not implemented yet.

## Architecture Decisions

Decision records live in `docs/decisions`.

- `0001-backend-foundation.md`
- `0002-database-foundation.md`
- `0003-text-ingestion.md`
- `0004-user-course-api.md`
- `0005-retrieval-foundation.md`

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
