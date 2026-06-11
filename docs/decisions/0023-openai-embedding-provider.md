# 0023 OpenAI Embedding Provider

## Status

Accepted

## Context

StudyBot already has vector and hybrid retrieval, but the default embedding
provider is deterministic and local. That is useful for tests and architecture,
but a portfolio-ready RAG demo needs a real embedding provider path.

The existing `document_chunk_embeddings` table already stores provider, model,
dimensions, and vector JSON. That lets fake and real embeddings coexist without a
schema change.

OpenAI's embeddings API accepts an input string, a model such as
`text-embedding-3-small`, and optional dimensions for supported models. It
returns a float vector that can be stored and compared with cosine similarity.

## Decision

Add an OpenAI embedding provider behind the existing embedding provider
interface.

The module includes:

- `OpenAIEmbeddingProvider`
- environment-driven provider selection:
  - `EMBEDDING_PROVIDER=fake`
  - `EMBEDDING_PROVIDER=openai`
- OpenAI API key configuration through `EMBEDDING_API_KEY` or `OPENAI_API_KEY`
- default OpenAI embedding model `text-embedding-3-small`
- optional `EMBEDDING_DIMENSIONS`
- mocked provider tests with no real API calls
- `503` responses for embedding provider configuration errors
- `502` responses for embedding provider runtime errors

When custom dimensions are configured, the stored model identifier includes the
dimension count so embeddings with different vector sizes do not share the same
provider/model key.

## Consequences

StudyBot can now run vector and hybrid retrieval with a real embedding provider
while keeping fake embeddings as the default for local development and tests.

Existing fake vectors remain valid. Switching to OpenAI creates separate
embeddings under the `openai` provider and configured model identifier.

`pgvector`, batch embedding jobs, provider usage/cost metrics, and embedding
quality evaluation with a larger dataset remain out of scope.
