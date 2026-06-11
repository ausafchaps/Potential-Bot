# 0021 Study Recommendations

## Status

Accepted

## Context

Weak-topic analytics identifies which quiz topics a learner struggles with, but
analytics alone does not tell the learner what to do next. StudyBot needs a
simple recommendation layer that converts weak-topic signals into concrete study
actions without requiring a new LLM call or new persistence tables.

## Decision

Add course-scoped study recommendations derived from weak-topic analytics.

The module includes:

- `GET /courses/{course_id}/study-recommendations`
- deterministic priority classification:
  - high
  - medium
  - low
  - mastered
- recommendation reasons based on quiz accuracy and attempted questions
- recommended actions:
  - review topic with a grounded-answer prompt
  - practice missed questions
  - generate another quiz
  - maintain mastered topics when requested
- `limit`, `min_attempts`, and `include_mastered` query filters

No migration is required because recommendations are derived from existing quiz
attempt and weak-topic analytics data.

## Consequences

StudyBot now turns quiz performance into action. The study loop becomes:
generate a quiz, submit an attempt, identify weak topics, and recommend what to
review or practice next.

This version is intentionally deterministic and read-only. Later versions can
persist recommendation events, track whether a student completed a
recommendation, use question-level concept tags, personalize recommendations by
user, and ask an LLM to generate richer review plans from cited course material.
