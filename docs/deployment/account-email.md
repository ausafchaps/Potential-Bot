# Account email delivery

The account-recovery feature can be merged and deployed with email disabled.
Before enabling real mail, configure and test a sender. No real reset or
verification messages are sent by tests or local previews.

For personal staging without a domain, a dedicated Gmail mailbox can send using
SMTP and an app password. The owner must enable 2-Step Verification and create
the app password themselves; never use the normal Gmail login password. See
[Google's app password requirements](https://support.google.com/mail/answer/185833).
Vercel permits outbound SMTP except port 25; see
[Vercel's SMTP guidance](https://vercel.com/kb/guide/serverless-functions-and-smtp).
Use a transactional provider and authenticated domain as the service grows.

Set Production-only secrets/settings on studybot-staging:

| Setting | Value |
| --- | --- |
| EMAIL_PROVIDER | smtp |
| SMTP_HOST | smtp.gmail.com |
| SMTP_PORT | 465 |
| SMTP_USERNAME | Dedicated sender's full Gmail address |
| SMTP_PASSWORD | Secret app password |
| EMAIL_FROM | Same Gmail address |
| PUBLIC_APP_URL | https://studybot-staging.vercel.app |
| SMTP_TIMEOUT_SECONDS | 5 |
| AUTH_REQUIRE_EMAIL_VERIFICATION | false during delivery verification |

Port 465 uses TLS immediately; port 587 requires STARTTLS with certificate checks.
Unencrypted SMTP and port 25 are unsupported. Store the app password only as a
server secret, never in frontend settings, screenshots, Git, or chat. Approve
transmission of account addresses and authentication links to the configured
email provider before connecting it.

Redeploy after setting environment values. Confirm `/auth/capabilities` enables
account email, then register a test account with an inbox you control. Confirm
receipt and the displayed canonical origin. Test verification, reset, replay,
expiration, and logout of old sessions. Verify in runtime logs that delivery has
no generic failures. Test again on Vercel after local success: SMTP background
tasks have no persistent queue or automatic retry. Do not enable required
verification until actual inbox delivery is working.

No existing accounts are silently marked verified by the migration. If required
verification is enabled later, students sign in and request a link before opening
their coursework. Disable required verification if sender delivery fails. Turning
email delivery off disables new requests while existing unexpired links can still
be redeemed. Outstanding links expire naturally; bounded cleanup prunes old rows.
