# Architecture

StudyBot is designed as a modular backend-first AI system.

The LLM should be the final reasoning layer, not the whole product. Documents,
chunks, retrieval results, generated study objects, feedback, and usage metrics
should be stored and inspected independently.

## Initial Modules

- API layer: FastAPI routes, request validation, and response formatting
- Core settings: environment-driven configuration
- Data layer: SQLAlchemy models, Alembic migrations, engine, and session management
- Document ingestion: upload, parsing, chunking, and metadata
- Retrieval: embeddings and cited evidence search
- Answer orchestration: grounded answers using retrieved context
- Study tools: quizzes, flashcards, attempts, and weak-topic tracking
- Analytics and evaluation: usage events and quality metrics

## First Implementation Boundary

Milestone 1 established the backend foundation:

- app construction
- health check endpoint
- settings object
- database session factory
- test setup

Milestone 2 starts the persistence model:

- users
- course workspaces
- documents
- document chunks
- Alembic migrations

Milestone 3 starts document ingestion:

- plain text upload
- UTF-8 decoding
- deterministic character chunking
- document status transitions
- persisted document chunks

Milestone 4 makes the core API flow usable:

- create users
- create course workspaces
- list a user's courses
- fetch users and courses by id
- upload text documents to API-created courses

Milestone 5 starts retrieval:

- course-scoped keyword search
- query tokenization
- term-frequency ranking
- source metadata for future citations
- retrieval tests for ranking and course isolation

Milestone 6 expands ingestion:

- shared ingestion helpers for text and PDF
- text-based PDF extraction
- page count metadata
- page-numbered chunks
- no OCR for scanned PDFs yet
