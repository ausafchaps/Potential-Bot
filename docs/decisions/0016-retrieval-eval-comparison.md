# 0016 Retrieval Eval Comparison

## Status

Accepted

## Context

StudyBot now has keyword, vector, and hybrid retrieval paths. The existing
retrieval evaluation module measured the keyword baseline only. Before switching
grounded answers to hybrid retrieval, the project needs a way to compare all
retrieval modes against the same dataset.

## Decision

Extend the retrieval evaluation module with mode comparison.

The comparison runner:

- loads the existing retrieval eval dataset
- seeds each eval case once
- runs keyword, vector, and hybrid retrieval against the same seeded course
- normalizes returned result types into an eval-friendly chunk shape
- reports per-mode metrics:
  - hit at k
  - mean reciprocal rank
  - precision at k
- reports best modes by metric
- exposes per-case results by retrieval mode

The original keyword-only `run_retrieval_evaluation` remains available and still
defaults to keyword mode.

## Consequences

The project can now inspect retrieval tradeoffs before changing answer behavior.
For the current deterministic fake embedding dataset, vector and hybrid retrieval
recover the synonym-style case that keyword misses, while keyword remains more
precise on the no-match case. That gives a more honest baseline for deciding when
hybrid retrieval should power grounded answers.

Persisted eval runs, dashboards, charts, external benchmarks, and LLM answer
quality evaluation remain out of scope.
