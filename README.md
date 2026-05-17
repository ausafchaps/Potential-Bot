# StudyBot

StudyBot is an auditable AI study assistant for students working with course notes,
PDFs, slides, assignments, and past papers.

The goal is to build a real AI engineering system, not a thin chatbot wrapper. The
system will ingest user documents, retrieve cited evidence, answer grounded
questions, generate quizzes and flashcards, track weak topics, and measure product
quality.

## Current Status

Milestone 1 is underway: backend foundation.

## Planned Capabilities

- Create course or subject workspaces
- Upload PDFs and text notes
- Parse and chunk documents
- Search uploaded material
- Answer questions with citations
- Generate quizzes and flashcards
- Track helpfulness feedback and usage metrics
- Evaluate retrieval and answer quality

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

