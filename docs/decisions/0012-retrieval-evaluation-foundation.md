# 0012 Retrieval Evaluation Foundation

## Status

Accepted

## Context

StudyBot has course-scoped keyword retrieval and grounded answers that depend on
retrieved chunks. Before adding embeddings, hybrid search, reranking, or real LLM
providers, the project needs a small way to measure whether retrieval returns
the expected source material.

## Decision

Add a local retrieval evaluation foundation.

The first evaluation module includes:

- a bundled JSON dataset: `retrieval_v1`
- direct seeding of eval users, courses, documents, and chunks into an in-memory
  database
- execution through the existing `search_course_chunks` service
- per-case results with returned chunks and expected targets
- aggregate metrics:
  - hit at k
  - mean reciprocal rank
  - precision at k
- failed-case summaries

No API endpoint, dashboard, migration, external benchmark, or LLM answer
evaluation is included in this module.

## Consequences

The project now has a measurable keyword-retrieval baseline. Exact keyword cases,
term-frequency ranking, PDF page metadata, distractor documents, no-match
behavior, and one intentional synonym limitation are covered by the seed dataset.

Future retrieval implementations can run against the same dataset to show whether
semantic or hybrid retrieval improves the system.
