# 0027 Authentication and resource ownership

## Status

Accepted

## Decision

Use email/password accounts with Argon2id password hashes through `pwdlib`.
Registration never accepts a role. Existing users retain their IDs and courses;
the migration gives them no password and a non-admin role. They cannot log in or
be claimed through public registration. An operator must set a password through
the trusted account-management command.

Issue random 256-bit bearer session tokens. Store only SHA-256 token hashes in
`auth_sessions` with user IDs and UTC expiry timestamps. Sessions last 24 hours
by default, configurable using `AUTH_SESSION_HOURS` (1-168 hours). Logout deletes
the current session immediately. Resetting a password through the operator
command revokes all of that account's sessions. Database-backed sessions work
across API processes without a shared signing secret.

Attach authentication and ownership dependencies to all coursework routers and
the private user endpoints. Resolve ownership through stored parents for direct
document, answer, question, quiz, attempt, and flashcard-set URLs. Foreign and
missing resources both return 404. Unauthenticated requests return 401 with a
Bearer challenge. Global admin metrics requires the database `is_admin` role and
returns 403 to other authenticated users. Admin status does not grant access to
another user's course material. Health and readiness remain public.

The frontend provides registration, login, logout, and a selector for the signed-in
account's courses. Tokens live in sessionStorage, are bound to the configured API
origin, and are cleared when the API changes or a session becomes invalid. Study
views are cleared on account and course switches. Metrics are shown only to admins.
Token responses use `Cache-Control: no-store`. API clients send Authorization
headers; authentication does not use cookies, so there is no ambient cookie-based
authorization or CSRF flow.

## Consequences

Apply `alembic upgrade head` before starting the updated API. The existing
`POST /users` endpoint remains as password-required registration returning a user;
clients must then log in. `/auth/register` returns a user and session together.
Tests and the staging smoke script use authenticated accounts.

This is an account/session foundation. Email verification, self-service password
recovery, MFA, OAuth sign-in, shared abuse throttling, and periodic expired-session
cleanup are separate follow-up work. Deploy behind HTTPS; enforce auth endpoint
request limits at the gateway before opening public registration to real users.
