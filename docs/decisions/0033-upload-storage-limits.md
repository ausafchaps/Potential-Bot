# Upload and stored note allowances

AI budgets do not bound document ingestion or stored notes. Bound uploaded files,
PDF pages, extracted characters, and stored chunk bytes, with student and project
allowances plus shared upload-attempt throttling.

Defaults: 2 MiB/file, 100 pages/PDF, 200,000 characters/document; 20 documents and
2 MiB of note text/student; 500 documents and 50 MiB of note text/project. Hourly
upload attempts: 10/student, 30/IP, 100/project. All limits are configurable and
positive; the file maximum is capped at 4 MiB. The API bounds the multipart body
before parsing to file maximum plus 64 KiB of overhead, even without a trustworthy
Content-Length. Serverless gateway limits may reject requests sooner.

Store the sum of UTF-8 bytes in the persisted chunks on each document, including
overlap. Migration 20261012_0013 backfills old records, including Unicode, without
changing text. Note allowances exclude embeddings, saved output/citation copies,
and database overhead; original files are not retained. They are not a full
database size quota. Existing over-limit accounts keep their work and can delete
documents until back within allowance.

A singleton database row serializes admission and deletion. The quota check,
document/chunk persistence, and commit are atomic; concurrent requests cannot
claim the same remaining capacity. PDF extraction happens before this lock.
Quota errors roll back the processing row; readable-content failures retain a
failed document with zero stored bytes. Failed records count toward slots.
Commit failures preserve the previous allowance. Reads use one snapshot query and
return only the student's counters plus a shared-capacity boolean.

The frontend shows remaining slots/text space and per-file limits, checks oversized
files before sending them, prevents duplicate upload clicks, and confirms deletion.
Saved study work remains after deletion through existing citation snapshots.
Quota checks stay authoritative on the server; cached frontend usage does not
prevent a retry after space is freed elsewhere. Temporary errors leave controls
retryable, and stale account/course responses cannot repaint another workspace.

Tests cover boundaries, Unicode/chunk overlap, migration preservation, failures,
auth ownership, throttling, delete/re-upload, and atomic SQLite/PostgreSQL uploads.
