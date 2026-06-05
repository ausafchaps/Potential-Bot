# 0015 Hybrid Retrieval Foundation

## Status

Accepted

## Context

StudyBot now has keyword retrieval and vector retrieval. Keyword search is
precise for exact course terms, while vector search can recover semantic matches
from the deterministic embedding foundation. The next retrieval step is to
combine both signals into one explainable ranked path.

## Decision

Add a hybrid retrieval service and endpoint:

- `GET /courses/{course_id}/search/hybrid`

The hybrid service:

- runs keyword retrieval
- runs vector retrieval
- merges candidates by `chunk_id`
- normalizes keyword score by max keyword score
- normalizes vector similarity by max vector similarity
- computes a weighted hybrid score
- defaults to `0.45` keyword weight and `0.55` vector weight
- exposes keyword score, vector similarity, normalized scores, matched terms, and
  retrieval sources

The existing keyword and vector endpoints remain unchanged. Grounded answer
orchestration also remains on keyword retrieval for this module so hybrid search
can be reviewed and evaluated before changing answer behavior.

## Consequences

The project now has an explainable retrieval path that can combine exact term
matching with semantic matching. Hybrid search can be compared against keyword
and vector retrieval before it becomes the default source for grounded answers.

Reranking, persisted retrieval runs, user-configurable weights, answer
orchestrator migration, and retrieval evaluation comparison dashboards remain out
of scope.
