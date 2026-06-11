# 0022 Flashcard Generation Foundation

## Status

Accepted

## Context

StudyBot can generate quizzes, grade attempts, identify weak topics, and provide
study recommendations. The next study-tool layer is flashcards: a cited review
format that gives learners another concrete action besides retaking quizzes.

Flashcards can reuse the same retrieval, provider, citation, persistence, and
deterministic testing patterns already established for grounded answers and
quizzes.

## Decision

Add a cited flashcard generation foundation.

The module includes:

- `flashcard_sets` table
- `flashcards` table
- `flashcard_citations` table
- `POST /courses/{course_id}/flashcard-sets`
- `GET /courses/{course_id}/flashcard-sets`
- `GET /flashcard-sets/{flashcard_set_id}`
- deterministic fake flashcard generation from hybrid-retrieved evidence
- a strict JSON prompt path for real LLM flashcard generation
- stored citation snapshots for generated flashcards
- persisted `insufficient_evidence` flashcard records when a topic lacks usable
  evidence

## Consequences

StudyBot now supports both practice and review study objects: quizzes for
testing recall and flashcards for reviewing cited material. This makes study
recommendations more actionable because weak topics can lead to either another
quiz or a flashcard review flow.

Flashcard review sessions, remembered/forgot ratings, spaced repetition,
editing/deleting flashcards, per-user progress, and frontend flashcard UI remain
out of scope.
