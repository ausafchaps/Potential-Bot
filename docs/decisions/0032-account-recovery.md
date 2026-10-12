# Email verification and password reset

Add single-use random account links and SMTP delivery behind explicit settings.
Migration 20261012_0012 adds verification state, credential version, and hashed
account tokens. Existing credentials and study data are preserved; no address is
automatically trusted. Delivery and mandatory verification default off.

Store only SHA-256 token hashes, email hashes, purpose, credential version, expiry,
and consumption time. Reset links last 15 minutes and verification links 24 hours.
Redeeming a token atomically claims it and conditionally updates the user in one
transaction. Password resets increment credential version and revoke all sessions;
older reset/verification links become invalid. Session creation locks/checks the
user's credential version and password hash so an in-flight old login cannot
create a session after reset. Operator password changes also increment the version.

Issue links from a configured origin, never a request Host header or client URL.
Use URL fragments, strip them before other requests, and keep tokens in memory
only. Require an explicit verification POST so link previews do not consume links.
Reset completion returns to sign-in. Legacy accounts without passwords cannot be
claimed through reset.

Reset requests have uniform public responses for known/unknown accounts; SMTP runs
after the response to reduce delivery-dependent timing. Shared database counters
bound IP, address, and project attempts. Resend requires sign-in. SMTP uses TLS and
sanitized failure logs. The response background task is not a durable queue, and
successful submission does not prove inbox delivery. A configured sender must be
verified end-to-end on Vercel before requiring email verification. SMTP credentials
and provider transmission require explicit approval during deployment setup.

Tests cover expiry, replay, purpose/email binding, revocation, parallel resets,
stale logins, optional verification gating, limits, secure SMTP, migration drift,
and safe frontend link handling. PostgreSQL CI tests concurrent redemption.
