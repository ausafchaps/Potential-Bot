# 0017 Hybrid Grounded Answers

## Status

Accepted

## Context

StudyBot has keyword, vector, and hybrid retrieval, plus an evaluation comparison
layer for retrieval modes. The grounded answer orchestrator still used keyword
retrieval only, which meant semantic matches available through hybrid retrieval
were not available to the user-facing question endpoint.

## Decision

Switch grounded answer orchestration to hybrid retrieval.

The module includes:

- hybrid retrieval as the evidence source for `POST /courses/{course_id}/questions`
- an internal grounded evidence adapter that preserves the existing response
  shape
- hybrid score conversion into the existing integer `score` response field
- citation and prompt construction from hybrid-retrieved chunks
- a minimum hybrid score threshold before answer generation
- unchanged `insufficient_evidence` response behavior when no evidence clears the
  threshold

The question API contract remains unchanged. Retrieval mode selection, stored
retrieval-run metadata, citation score storage, and user-configurable thresholds
remain out of scope.

## Consequences

Grounded answers can now use evidence found through combined keyword and vector
signals. This lets synonym-style questions retrieve relevant chunks that keyword
retrieval alone would miss, while low-confidence hybrid matches are filtered to
protect the insufficient-evidence path.
