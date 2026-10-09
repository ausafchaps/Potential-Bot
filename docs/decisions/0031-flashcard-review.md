# Flashcard review and spaced repetition

Stored flashcards previously had no review progress or next review time. Add a
Review tab with a course-scoped queue, answer reveal, citations, and four ratings.
Loading the queue or rating a card never calls an AI provider.

Persist one `flashcard_progress` row per card and student, with total review count,
last rating, interval, review time, and due time. Migration `20261009_0011` adds this
table; existing cards are immediately due because they have no progress row.
Foreign keys cascade when cards or students are deleted. Historical study content
is preserved by upgrade/downgrade; downgrade discards review progress only.

Use epoch seconds for consistent UTC scheduling across SQLite and PostgreSQL.
Again schedules 10 minutes. Hard, Good, and Easy use the larger of their initial
1/3/7-day interval and the previous interval multiplied by 1.2/2/3, rounded up to a
minute, capped at 365 days. Again resets the interval. This is an intentionally
simple heuristic, not an implementation of FSRS or SM-2.

Queue only cards due at or before the current server time, including overdue and
never-reviewed cards. Prioritize oldest due time, then creation time and ID. Return
at most 50 cards plus total, ever-reviewed, due-now counts and earliest future due
time. The frontend refetches after each accepted rating and asks students to
refresh when their next card becomes due. Future cards are not reviewed early.

Protect course and direct card routes through persisted ownership. Rating payloads
contain the queue's review-count version. A conditional UPSERT atomically accepts
one submission for that version and due time; stale or duplicate submissions
return 409. The browser disables ratings during submission and refetches on 409.
Network errors retain the revealed card for retry; a committed-but-lost response
will produce a version conflict on retry rather than rescheduling. Database errors
roll back and return a generic 503. Workspace versions reject late responses after
course/account/API changes. The table holds only the latest rating, not event history.

Validate schedules, UTC boundaries, progress persistence, ownership, pagination,
concurrent submissions, migrations, and foreign-key cleanup on SQLite; CI also
checks first and subsequent concurrent reviews on PostgreSQL. Frontend tests cover
reveal, safe citations, rating requests, duplicate clicks, failures, conflicts,
empty/loading states, and workspace isolation.
