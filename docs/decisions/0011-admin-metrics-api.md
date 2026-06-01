# 0011 Admin Metrics API

## Status

Accepted

## Context

StudyBot now stores users, courses, documents, chunks, questions, answers,
citations, and feedback. The project needs a lightweight way to inspect usage
and quality signals before building a frontend dashboard.

## Decision

Add a read-only admin metrics endpoint:

- `GET /admin/metrics`

The endpoint returns:

- usage counts
- document status breakdown
- document content type breakdown
- average chunks per document
- answer status breakdown
- citation coverage rate
- average feedback rating
- feedback rating distribution

Authentication and time-window filtering remain out of scope.

## Consequences

This gives the project early product and quality metrics that can later support
admin dashboards, portfolio reporting, and early user monitoring.

