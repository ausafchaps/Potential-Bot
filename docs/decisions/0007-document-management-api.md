# 0007 Document Management API

## Status

Accepted

## Context

StudyBot can ingest text and text-based PDFs, persist chunks, and search them.
Before adding LLM answers, the API needs visibility and control over uploaded
documents.

## Decision

Add document management endpoints:

- `GET /courses/{course_id}/documents`
- `GET /documents/{document_id}`
- `GET /documents/{document_id}/chunks`
- `DELETE /documents/{document_id}`

Document deletion removes associated chunks through the existing SQLAlchemy
relationship cascade.

## Consequences

This makes the backend easier to inspect, test, and operate before answer
generation. It also gives later frontend and admin views a stable API for
document status, page counts, chunk counts, and extracted chunk text.

