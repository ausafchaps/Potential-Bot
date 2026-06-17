# 0024 Frontend Demo

## Status

Accepted

## Context

StudyBot has a strong backend portfolio story, but reviewers need a quick way to
see the product loop without reading API docs. A full production frontend with
auth, routing, and deployment would be too large for this slice.

The backend already exposes enough API surface to demonstrate the end-to-end
learning loop: workspace creation, document ingestion, grounded answers, quizzes,
grading, weak-topic analytics, study recommendations, flashcards, and metrics.

## Decision

Add a local static frontend demo in `frontend/`.

The module includes:

- dependency-free HTML, CSS, and JavaScript
- local CORS support for `http://127.0.0.1:5173` and `http://localhost:5173`
- a single workspace surface for creating users and courses
- document upload for text and PDF files
- grounded Q&A with citations
- quiz generation and attempt submission
- weak-topic and study recommendation views
- flashcard generation
- document summaries and admin metric summaries

The frontend keeps the current backend's explicit user/course ID model and does
not add authentication.

## Consequences

StudyBot can now be shown as a usable local product demo while preserving the
backend-first architecture. The frontend is intentionally thin: backend APIs
remain the source of product behavior and validation.

Production auth, frontend routing, package-managed React, deployment, and
flashcard review progress remain out of scope.
