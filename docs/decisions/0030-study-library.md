# Study library

The backend persists generated study material, but the frontend previously only
displayed the latest generation. Students could not revisit it after reloading.

Add a course-scoped Library tab that combines the existing question, quiz, and
flashcard-set list APIs. Sort newest first, filter by type and text, and display
20 records per page. Course selection in the workspace scopes the whole library.
Pagination and text filters operate on the fetched lists; server pagination is a
future improvement for large libraries.

Opening a question loads its answer versions and the selected answer's citations.
Opening a quiz restores its questions and lists its saved attempts; students can
review a previous score or submit a new attempt. Opening a flashcard set restores
its stored cards. These actions only call authenticated GET endpoints, require no
new provider calls, and consume no generation allowance. Existing ownership checks
apply. No database migration is needed.

Refresh when entering the Library or changing the selected course. Clear saved
views on course/account/API changes. Workspace and request versions prevent late
loads from displaying stale records after switching courses or opening another
item. Show loading, empty, filtered-empty, and retry messages; escape stored text
before inserting it into HTML.

Validate with dependency-free Node.js tests for filtering, paging, safe rendering,
read-only reopening, error states, and delayed-response isolation. CI runs these
checks alongside backend tests. Browser checks cover reload, reopening each type,
score review, course switching, and sign-out.
