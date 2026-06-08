# 0018 Quiz Generation Foundation

## Status

Accepted

## Context

StudyBot now has a strong retrieval and grounded-answer backend. The next product
step is to build an actual study feature on top of that RAG infrastructure.
Quizzes are a natural first feature because they can reuse hybrid retrieval,
provider selection, citation snapshots, and persistence patterns already used by
answers.

## Decision

Add a multiple-choice quiz generation foundation.

The module includes:

- `quizzes` table
- `quiz_questions` table
- `quiz_question_options` table
- `quiz_citations` table
- `POST /courses/{course_id}/quizzes`
- `GET /courses/{course_id}/quizzes`
- `GET /quizzes/{quiz_id}`
- deterministic fake quiz generation from hybrid-retrieved evidence
- a strict JSON prompt path for real LLM quiz generation
- stored citation snapshots for generated quiz questions
- persisted `insufficient_evidence` quiz records when a topic lacks usable
  evidence

Quiz attempts, grading, weak-topic tracking, flashcards, editing/deleting
quizzes, streaming generation, frontend work, and advanced difficulty calibration
remain out of scope.

## Consequences

StudyBot now has its first generated study-tool feature, not only question
answering. The fake path keeps tests deterministic, while the stored quiz and
citation structure is ready for real provider output and later attempt/scoring
features.
