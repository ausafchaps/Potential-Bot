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

Milestone 7 adds document management:

- list documents for a course
- inspect document summaries
- inspect extracted chunks
- delete documents and their chunks

Milestone 8 starts grounded answers:

- course-scoped question endpoint
- question, answer, and citation persistence
- provider interface for LLMs
- deterministic fake LLM provider
- prompt construction from retrieved chunks
- structured citations

Milestone 9 starts answer quality feedback:

- answer feedback events
- 1-5 helpfulness rating
- optional comments
- answer-level quality signal for future analytics

Milestone 10 adds answer history:

- list course questions
- inspect question answers
- inspect answer citations and feedback
- summarize feedback counts and average rating

Milestone 11 adds admin metrics:

- usage counts
- document status and type breakdowns
- answer status and citation coverage
- feedback averages and rating distribution

Milestone 12 starts retrieval evaluation:

- bundled retrieval eval dataset
- in-memory seeding of eval courses, documents, and chunks
- hit at k
- mean reciprocal rank
- precision at k
- failed-case summaries for keyword retrieval limitations

Milestone 13 adds real LLM provider integration:

- provider factory driven by environment settings
- fake provider remains the default
- Groq provider using OpenAI-compatible chat completions
- provider configuration and runtime errors surfaced through the question API
- mocked HTTP tests for provider request and response handling

Milestone 14 starts vector retrieval:

- persisted document chunk embeddings
- deterministic fake embedding provider
- lazy embedding creation for completed course chunks
- cosine similarity ranking
- course-scoped vector search endpoint
- SQLite-compatible vector storage before `pgvector`

Milestone 15 starts hybrid retrieval:

- course-scoped hybrid search endpoint
- keyword and vector candidate merging by chunk id
- normalized keyword and vector scores
- weighted hybrid score
- retrieval source metadata for explainability
- answer orchestration still uses keyword retrieval until hybrid is evaluated

Milestone 16 expands retrieval evaluation:

- comparison reports for keyword, vector, and hybrid retrieval
- each eval case is seeded once before all retrieval modes run
- per-mode hit at k, mean reciprocal rank, and precision at k
- best-mode summaries by metric
- per-case mode results that expose retrieval tradeoffs

Milestone 17 switches grounded answers to hybrid retrieval:

- answer orchestration uses hybrid retrieval for evidence
- public question response shape remains unchanged
- hybrid chunks are adapted into grounded evidence chunks for prompts and citations
- low-confidence hybrid results are filtered before answer generation
- insufficient-evidence responses remain supported

Milestone 18 starts quiz generation:

- stored quizzes, quiz questions, options, and quiz citations
- course-scoped quiz generation endpoint
- quiz list and detail endpoints
- deterministic fake quiz generation from hybrid evidence
- real-provider JSON prompt path for future Groq quiz generation
- insufficient-evidence quiz records when retrieval cannot support a topic
