# Architecture

StudyBot is designed as a modular backend-first AI system.

The LLM should be the final reasoning layer, not the whole product. Documents,
chunks, retrieval results, generated study objects, feedback, and usage metrics
should be stored and inspected independently.

## Initial Modules

- API layer: FastAPI routes, request validation, and response formatting
- Core settings: environment-driven configuration
- Data layer: SQLAlchemy engine and session management
- Document ingestion: upload, parsing, chunking, and metadata
- Retrieval: embeddings and cited evidence search
- Answer orchestration: grounded answers using retrieved context
- Study tools: quizzes, flashcards, attempts, and weak-topic tracking
- Analytics and evaluation: usage events and quality metrics

## First Implementation Boundary

Milestone 1 only establishes the backend foundation:

- app construction
- health check endpoint
- settings object
- database session factory
- test setup

