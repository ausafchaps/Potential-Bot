# Course study dashboard

Students previously had to visit Review, Library, Quiz, and Plan separately to
decide what to study. Add a Dashboard as the initial view, following the course
selected in Workspace. On mobile the signed-in study pane appears before the
workspace controls; actions that need notes move focus to the upload control.

The authenticated GET `/courses/{course_id}/dashboard` combines existing data:
completed document count; flashcard due count, total, and next future review;
quiz-attempt count and latest five results; up to five weak topics; the six newest
usable saved items; and a deterministic next study action. Ownership and optional
email verification use the existing private-resource dependency. Responses use
no-store, database failures return a safe retryable error, and neither generation
providers nor AI-usage reservations are called. No new tables or migration.

New cards and progress due at or before the current UTC instant are due, using
the same definition as Review. Analytics reuses the existing topic aggregation;
topics with no incorrect answers are omitted from the weak-topic list. Saved
items are answered questions, generated quizzes with questions, and generated
flashcard sets with cards. Insufficient-evidence and empty results remain in
Library but are not offered as ready work in Dashboard. Lists have stable
timestamp/ID ordering and bounded payloads; full totals are computed in SQL.

The next action prioritizes due cards, then a weak topic's saved quiz, then a
prepared explanation question when notes exist, then the newest saved work.
Courses with notes but no saved work prepare a question; empty courses point to
uploading notes. Preparing a question does not send it. Opening a score or saved
item uses existing GET views; explicit Ask/Generate actions alone use AI.

The dashboard refreshes on entry, sign-in, restore, course changes, manual refresh,
and visible study mutations. Account/API/course changes clear private data and
invalidate delayed responses. Existing saved-view guards also protect multi-step
score opens from overriding a newer selection. Empty, unverified, signed-out,
and unavailable states explain how to proceed without invented progress.

Validation covers ownership, course isolation, due boundaries, bounded history,
recommendation priority, no AI use, retry and stale responses, saved view routing,
and desktop/mobile layout. PostgreSQL CI exercises the combined dashboard query.
