# 0009 Answer Feedback API

## Status

Accepted

## Context

StudyBot can now generate grounded fake-LLM answers with citations. To make
answer quality measurable before onboarding real users, the backend needs a
lightweight feedback primitive.

## Decision

Add answer feedback events with a 1-5 rating and optional comment.

The module includes:

- `AnswerFeedback` model
- `POST /answers/{answer_id}/feedback`
- rating validation from 1 to 5
- optional normalized comment
- support for multiple feedback events per answer

## Consequences

This creates a simple quality signal that can power later analytics, admin
metrics, and answer improvement work. Multiple feedback events keep the model
event-like and ready for multiple users or repeated feedback.

