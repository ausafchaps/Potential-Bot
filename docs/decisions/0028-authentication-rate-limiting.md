# 0028 Shared authentication rate limiting

## Status

Accepted

## Decision

Use the existing PostgreSQL database for atomic fixed-window authentication
counters. SQLite implements the same behavior for local development and tests.
No additional service or secret is required. Migration `20261005_0009` adds only
`auth_rate_limits` and preserves users, coursework, and existing sessions.

Default login budgets are 30 attempts per client IP and 10 per normalized email
per 900 seconds. Signup has one shared budget of 10 attempts per IP per 3600
seconds across `POST /auth/register` and `POST /users`. Positive environment
settings control these budgets and windows. Successes, duplicate registrations,
and failed credentials all consume attempts. IP dependencies run before body
field validation and password work; email throttling runs after login validation
and before verification. Malformed JSON is rejected by FastAPI before dependencies
and must also be limited at the gateway.

Bucket keys hash the scope, identity, and aligned window start. The table stores
only a SHA-256 key, attempt count, and Unix expiry time. These hashes are not
encryption and should still be treated as internal operational data. Conditional
UPSERTs increment only below the budget, preventing concurrent oversubscription
and integer overflow. Counters commit before credential or account operations,
so failed login/registration does not undo them. Blocked requests cannot extend
expiry. Each counter transaction removes at most 100 buckets expired more than
24 hours ago using an expiry index. Cleanup occurs on traffic; quiet deployments
retain expired counters until the next authentication requests.

Return 429 with `Cache-Control: no-store`, a numeric `Retry-After`, and a generic
message containing the wait time. Unknown and existing email addresses use the
same policy. Database failures return generic 503 responses before password work.
Expose `Retry-After` through CORS. The existing frontend already displays error
messages, so it can show this wait time without changing session state.

Use the ASGI client address by default and ignore caller-supplied forwarding
headers. Vercel's server-side `VERCEL=1` system variable selects Vercel mode, which
uses only its platform `x-vercel-forwarded-for` header. An explicit
`AUTH_CLIENT_IP_SOURCE` override supports deployment configuration. In Vercel
mode, invalid or missing IP headers fail closed. Canonicalize IPv6 and mapped
IPv4 addresses before hashing. Do not enable Vercel mode on a server reachable
outside its gateway. Other proxy deployments must configure the ASGI server's
trusted proxy addresses instead of trusting arbitrary `X-Forwarded-For` values.

References: [Vercel request headers](https://vercel.com/docs/headers/request-headers),
[Vercel system variables](https://vercel.com/docs/environment-variables/system-environment-variables),
and [SQLAlchemy PostgreSQL UPSERT](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert).

## Consequences

Apply migrations before serving the updated API. Vercel's existing build step
does this on deployment after merge. Private endpoints, session validation, and
logout are outside these budgets. Operators can tune limits for shared campus
networks. Email limits reduce attempts across rotating IPs but can temporarily
throttle a legitimate account targeted by an attacker. Fixed windows permit a
burst at boundaries; this is throttling rather than permanent account lockout.
Keep gateway limits for request volume, malformed/oversized bodies, and database
load. This change does not add email verification or password recovery.

Tests cover shared endpoint budgets, normalization, successful and failed
attempts, expiry and retry times, spoofed headers, Vercel configuration, bounded
cleanup, storage failure, migration reversibility, and concurrent admission on
SQLite and PostgreSQL.
