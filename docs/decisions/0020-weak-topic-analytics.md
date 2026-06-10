# 0020 Weak Topic Analytics

## Status

Accepted

## Context

StudyBot can generate quizzes and store graded attempts. Those attempts contain
the core signals needed for learning analytics: quiz topic, question count,
correct answers, incorrect answers, and attempt timestamps. The next step is to
turn that stored grading data into product intelligence that helps identify what
a learner should review next.

## Decision

Add course-scoped weak-topic analytics from quiz attempts.

The module includes:

- `GET /courses/{course_id}/weak-topics`
- topic-level aggregation by quiz topic
- total attempted topics, attempts, and questions
- per-topic:
  - attempt count
  - question count
  - correct count
  - incorrect count
  - accuracy rate
  - weakness score
  - average score percent
  - last attempted timestamp
- sorting by weakest topics first
- `limit` and `min_attempts` query filters

No migration is required because this is read-only analytics over existing quiz
and quiz attempt tables.

## Consequences

StudyBot now closes a stronger study loop: generate a quiz, submit answers,
store graded attempts, and identify weak topics for review.

The first version treats the generated quiz topic as the analytics topic. Later
versions can add explicit question-level concepts, learning objectives, spaced
repetition signals, per-user analytics, trend windows, and recommendation
generation.
