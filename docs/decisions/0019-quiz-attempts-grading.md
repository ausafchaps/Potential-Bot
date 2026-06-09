# 0019 Quiz Attempts And Grading

## Status

Accepted

## Context

StudyBot can generate multiple-choice quizzes with citations. To make quizzes a
real study loop rather than static generated content, students need to submit
answers and receive measurable scores. Attempt data also gives future analytics
and weak-topic tracking a concrete foundation.

## Decision

Add quiz attempts and grading.

The module includes:

- `quiz_attempts` table
- `quiz_attempt_answers` table
- `POST /quizzes/{quiz_id}/attempts`
- `GET /quizzes/{quiz_id}/attempts`
- `GET /quiz-attempts/{attempt_id}`
- validation that each generated quiz question is answered exactly once
- validation that selected options belong to their questions
- score calculation from correct answers
- per-answer snapshots of:
  - question text
  - selected option text
  - correct option text
  - correctness

Attempts are not allowed for `insufficient_evidence` quizzes because those
quizzes do not have generated questions.

## Consequences

StudyBot now has a measurable study loop: generate a quiz, submit answers, and
store graded results. The snapshot approach keeps attempt history auditable even
if quiz content changes later.

Weak-topic tracking, per-user auth, retake policies, time limits, spaced
repetition, and frontend quiz-taking UI remain out of scope.
