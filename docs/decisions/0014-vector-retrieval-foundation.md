# 0014 Vector Retrieval Foundation

## Status

Accepted

## Context

StudyBot has keyword retrieval, retrieval evaluation, and real LLM provider
support. The next retrieval improvement is a semantic search path that can be
measured and evolved before introducing a production vector database or external
embedding APIs.

## Decision

Add a vector retrieval foundation using persisted chunk embeddings and a
deterministic local embedding provider.

The module includes:

- `document_chunk_embeddings` table
- embedding provider interface
- deterministic `FakeEmbeddingProvider`
- lazy generation of missing embeddings for completed course chunks
- SQLite-compatible vector storage as JSON text
- cosine similarity ranking
- course-scoped endpoint:
  - `GET /courses/{course_id}/search/vector`
- tests for embedding creation, idempotency, course isolation, ranking, and API
  errors

Real embedding providers, `pgvector`, hybrid retrieval, reranking, automatic
background embedding jobs, and frontend search mode selection remain out of
scope.

## Consequences

The backend now has a separate vector retrieval path that can be compared with
keyword retrieval and later upgraded to real embeddings. The fake embedding
provider is deterministic and intentionally simple; it validates storage,
similarity ranking, endpoint behavior, and architecture without external cost or
network dependency.
