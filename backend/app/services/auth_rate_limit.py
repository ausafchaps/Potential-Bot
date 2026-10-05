"""Atomic, database-backed fixed windows shared by all API instances."""

import hashlib
import math
import time
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AuthRateLimit


@dataclass(frozen=True)
class AttemptLimit:
    scope: str
    identity: str
    limit: int
    window_seconds: int


class AuthRateLimited(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__("Too many authentication attempts")


class AuthRateLimitUnavailable(Exception):
    pass


def consume_attempts(db: Session, limits: list[AttemptLimit]) -> None:
    """Commit counters before credential work, including attempts that later fail.

    A conditional UPSERT admits at most `limit` requests per bucket even when
    requests race across processes. All windows align to Unix time. Blocked
    requests cannot extend a window or overflow the counter.
    """
    now = time.time()
    retry_after = 0
    try:
        dialect = db.get_bind().dialect.name
        if dialect not in {"postgresql", "sqlite"}:
            raise AuthRateLimitUnavailable("Unsupported rate-limit database")
        insert = postgres_insert if dialect == "postgresql" else sqlite_insert
        # Bounded cleanup keeps one-off identities from accumulating indefinitely.
        # Retain a day beyond expiry so cleanup does not contend with live windows.
        expired = (
            select(AuthRateLimit.bucket_key)
            .where(AuthRateLimit.expires_at < int(now) - 86400)
            .order_by(AuthRateLimit.expires_at, AuthRateLimit.bucket_key)
            .limit(100)
        )
        db.execute(delete(AuthRateLimit).where(AuthRateLimit.bucket_key.in_(expired)))
        for policy in limits:
            window_start = int(now) // policy.window_seconds * policy.window_seconds
            expires_at = window_start + policy.window_seconds
            # Persist neither plaintext addresses nor plaintext emails/passwords.
            key = hashlib.sha256(
                f"{policy.scope}\0{policy.identity}\0{window_start}".encode()
            ).hexdigest()
            statement = insert(AuthRateLimit).values(
                bucket_key=key, attempts=1, expires_at=expires_at
            )
            statement = statement.on_conflict_do_update(
                index_elements=[AuthRateLimit.bucket_key],
                set_={"attempts": AuthRateLimit.attempts + 1},
                where=AuthRateLimit.attempts < policy.limit,
            ).returning(AuthRateLimit.attempts)
            if db.scalar(statement) is None:
                retry_after = max(retry_after, max(1, math.ceil(expires_at - now)))
                # Do not create arbitrary email buckets once the IP is blocked.
                break
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise AuthRateLimitUnavailable("Authentication throttling unavailable") from exc
    if retry_after:
        raise AuthRateLimited(retry_after)
