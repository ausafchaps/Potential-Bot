# 0010 Answer History API

## Status

Accepted

## Context

StudyBot stores questions, answers, citations, and feedback, but clients need a
read API to inspect that history after an answer is generated.

## Decision

Add read-only answer history endpoints:

- `GET /courses/{course_id}/questions`
- `GET /questions/{question_id}`
- `GET /answers/{answer_id}`
- `GET /answers/{answer_id}/citations`
- `GET /answers/{answer_id}/feedback`

Course question history is returned newest first. Answer summaries include
citation count, feedback count, and average rating.

## Consequences

This supports future chat/history views, answer debugging, and user-facing review
flows without adding new persistence tables. Pagination and permissions remain
out of scope until real usage requires them.

