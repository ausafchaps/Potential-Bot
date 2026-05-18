# 0003 Text Ingestion

## Status

Accepted

## Context

Document ingestion should move in small modules. The first useful version only
needs to prove that a course can receive uploaded material, extract text,
generate deterministic chunks, and persist those chunks for later retrieval.

## Decision

Support plain text ingestion first.

The first ingestion module includes:

- `POST /courses/{course_id}/documents/text`
- UTF-8 text decoding
- fixed-size character chunking with overlap
- persisted `Document` and `DocumentChunk` records
- document status transitions to `completed` or `failed`
- tests for chunking and upload behavior

PDF parsing, embeddings, vector search, citations, and LLM answers remain out of
scope for this module.

## Consequences

This keeps ingestion deterministic and easy to verify. Character-based chunking
is less precise than token-aware chunking, but it is enough to validate the
document persistence pipeline before choosing embedding and LLM tooling.

