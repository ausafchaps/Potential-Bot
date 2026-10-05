# 0029 AI usage limits

## Status

Accepted

## Context

The staging app now calls a real Groq provider. Authentication throttling does not
limit signed-in students' generation requests or protect a shared AI allowance.

## Decision

Add dedicated database-backed fixed-window AI counters for real provider calls.
Answers, quizzes, and flashcard sets share per-user and project minute/day budgets.
Defaults are 3/minute and 20/day per student, 10/minute and 100/day per project.
Positive settings tune the counts; days reset at midnight UTC and admins follow
the same policy. Atomic conditional UPSERTs commit all budgets together before
provider work; any exhausted budget rolls back the entire reservation.

Only calls with usable evidence consume a reservation. Fake providers are exempt.
Provider failures count, since requests may still consume provider resources.
Counter failures stop generation with a generic 503. Quota failures return 429,
the longest applicable retry delay, and no-store headers. Groq 429s are mapped to
a readable provider-limit message without exposing provider details.

Expose authenticated self-only usage at `/auth/ai-usage`. Show daily/minute
remaining allowance and the daily reset in the frontend, refreshing after each
generation. Persist hashes of scope/identity/window, counts, and expiry only.
Clean at most 100 buckets expired more than a day ago per admitted request.

## Consequences

Instances share counters through PostgreSQL. Existing material remains accessible
when generation is blocked. SQLite supports local tests; PostgreSQL concurrency
is covered in CI. Migration `20261005_0010` must run before the new code serves.

This is attempt metering, not exact token accounting or an overall request-load
firewall. Provider token limits, other organization consumers, retrieval/embedding
costs, and uploads are outside this budget. Fixed windows allow boundary bursts.
Migration downgrade removes usage history and should not be used as a quota reset.
