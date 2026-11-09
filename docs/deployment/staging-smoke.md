# Automated staging smoke checks

After this change is merged, `.github/workflows/staging-smoke.yml` checks
`https://studybot-staging.vercel.app` following successful Vercel Production
deployment statuses. Production is Vercel's environment name for this **staging**
project. No GitHub secrets, paid service, persistent test accounts, or database
credentials are needed. Existing Groq and Neon connections are used by the app.

The workflow checks out trusted `main` and skips deployments whose SHA is not its
current HEAD. It accepts only statuses created by `vercel[bot]` for deployments
created by `vercel[bot]`, in this repository's Production environment, whose URL
identifies the `studybot-staging` project in `ausaf2` (or its canonical alias).
It waits up to five minutes for the canonical URL's `/health` revision to match. Preview
URLs and URLs supplied by deployment payloads are never used. Keep Vercel's
automatic system environment variables enabled so `VERCEL_GIT_COMMIT_SHA` is
available. `/health` exposes only a validated full commit SHA.

## What a run checks

The script exercises the API over HTTP using two randomly named temporary students:

- Health, database readiness, registration, password login, session identity and logout.
- Course and saved-work privacy between the two students and unauthenticated access.
- Text ingestion, persisted chunks, storage accounting, oversized-file rejection,
  and releasing storage by deleting the uploaded document.
- One cited answer, one three-question quiz and one three-card flashcard set.
- Quiz grading, saved history, weak-topic analytics, flashcard review persistence,
  due dates, and the course dashboard's counts and scores.
- AI usage accounting and validation rejection without spending AI allowance;
  reading, grading, reviewing and deleting saved work must consume no generations.
- Saved answer/citation snapshots after deleting the source document.
- Deletion of both temporary accounts and revocation of their sessions/logins.

A passing run makes **three generation requests**. Requests are not retried, and
failures can still consume allowance. The shared daily/minute budgets remain in
force. Live checks never deliberately exhaust those shared budgets. Low-limit
AI rejection and storage admission tests run with isolated databases in normal
CI instead. This smoke test checks API behavior, not browser rendering or PDF
extraction; those have separate tests/manual checks.

Account email delivery and required verification must remain disabled. The
runner stops before registration if either is enabled, to avoid sending email
to synthetic addresses. Enabling email later requires adapting these checks.

## Cleanup and safety

Each run generates passwords in memory and uses `DELETE /auth/account` in a
`finally` block on success or failure. The endpoint requires a current bearer,
the student's current password, and `confirmation: "delete-my-account"`. It
accepts no target user ID. Administrator accounts cannot be deleted. Attempts
are limited to five per student per 15 minutes; database failures fail closed.
Credential changes invalidate an in-flight deletion. This API is permanent
self-deletion and has no frontend control in this change.

Database foreign-key cascades remove sessions, account links, owned courses,
documents/chunks, answers/citations/feedback, quizzes/attempts and cards/progress
atomically. SQLite connections now enable foreign-key enforcement, matching
PostgreSQL; deletion refuses SQLite connections without enforcement. The storage
lock serializes deletion with quota admission. No new migration is required.

Hashed authentication/AI usage counters expire through their existing bounded
cleanup. Deleting a student does **not** refund shared AI allowance or clear
project throttles. No credentials or response bodies are printed or uploaded as
artifacts. Redirects are refused, including for authenticated requests.

Runs are serialized and do not cancel active runs, allowing cleanup to finish.
The study flow has a six-minute deadline, requests time out, and cleanup has its
own bounded allowance. A process kill, manual cancellation or extended outage
can still prevent cleanup. A cleanup failure makes the job fail and prints only
the synthetic account addresses containing the run ID. An operator can locate
those exact `staging-smoke-<run-id>-<index>@example.com` accounts in the staging
database and remove them with their dependent records after checking ownership.
Never delete real student accounts as part of smoke-test cleanup.

## Run and diagnose

In GitHub **Actions → Staging smoke**, inspect the job after a merge/deployment.
Failures are visible there; no separate alert service is configured. For a
manual rerun, choose **Run workflow**, branch **main**, after its deployment is
healthy. This spends another three generations if it succeeds. The workflow
will not run manually from a feature branch.

Locally, against current staging:

```powershell
python scripts/staging_smoke.py --expected-revision FULL_MAIN_COMMIT_SHA --wait-seconds 300
```

For a local server using fake AI and an isolated database:

```powershell
python scripts/staging_smoke.py --base-url http://127.0.0.1:8000 --allow-fake-ai
```

Only the canonical staging HTTPS origin and loopback HTTP servers are accepted.
Fake AI is allowed only on loopback. A failed revision check creates no accounts.
For an HTTP 429, read the app's usage state and wait for the relevant window;
do not raise limits or disable throttling to make the job pass. For cleanup
failure, inspect that run before triggering more runs. For a revision mismatch,
check that Vercel deployed current `main` and promoted the canonical alias.

The runner uses only Python's standard library. CI also runs its full HTTP flow
against an isolated SQLite API, metered-provider stubs and injected failure
responses, and tests cleanup against migrated PostgreSQL.

Event references: [Vercel for GitHub](https://vercel.com/docs/git/vercel-for-github)
and [GitHub deployment status events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#deployment_status).
