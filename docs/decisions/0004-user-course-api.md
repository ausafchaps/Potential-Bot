# 0004 User and Course API

## Status

Accepted

## Context

Text ingestion already requires a `course_id`, but the API did not yet expose a
normal way to create users or courses. The next module should make the core flow
usable without direct database seeding.

## Decision

Add explicit user-id based APIs without authentication for now.

The module includes:

- `POST /users`
- `GET /users/{user_id}`
- `POST /users/{user_id}/courses`
- `GET /users/{user_id}/courses`
- `GET /courses/{course_id}`
- service-layer ownership checks
- duplicate email handling

Authentication, invite codes, sessions, passwords, and JWTs remain out of scope.

## Consequences

This makes the local MVP flow usable while avoiding premature auth complexity.
The API contract can later be wrapped with invite-based access or full auth
without changing the core `User`, `Course`, `Document`, and `DocumentChunk`
relationships.

