"""Reserve real generation attempts atomically before calling an AI provider."""

import hashlib
import math
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AIUsageBucket, Course
from app.schemas.ai_usage import AIUsageResponse, AIUsageWindow


@dataclass(frozen=True)
class GenerationBudget:
    scope: str
    identity: str
    limit: int
    window_seconds: int
    message: str


class AIUsageLimited(Exception):
    def __init__(self, retry_after: int, message: str):
        self.retry_after = retry_after
        super().__init__(message)


class AIUsageUnavailable(Exception):
    pass


def bucket_key(policy: GenerationBudget, now: float) -> str:
    start = int(now) // policy.window_seconds * policy.window_seconds
    return hashlib.sha256(
        f"{policy.scope}\0{policy.identity}\0{policy.window_seconds}\0{start}".encode()
    ).hexdigest()


def user_budgets(user_id: uuid.UUID) -> list[GenerationBudget]:
    return [
        GenerationBudget("user-minute", str(user_id), settings.ai_user_minute_limit, 60,
                         "You have reached your AI limit for this minute."),
        GenerationBudget("user-day", str(user_id), settings.ai_user_daily_limit, 86400,
                         "You have used today's AI generation allowance."),
    ]


def consume_generation(db: Session, user_id: uuid.UUID) -> None:
    """All budgets commit together; blocked requests consume no other budget.

    Counters survive provider failures because a timed-out call may still use
    provider resources. Fixed windows align to UTC minutes and days.
    """
    now = time.time()
    policies = [
        GenerationBudget("project-minute", "project", settings.ai_project_minute_limit, 60,
                         "StudyBot has reached its shared AI limit for this minute."),
        GenerationBudget("project-day", "project", settings.ai_project_daily_limit, 86400,
                         "StudyBot has used today's shared AI generation allowance."),
        *user_budgets(user_id),
    ]
    blocked: tuple[int, str] | None = None
    try:
        dialect = db.get_bind().dialect.name
        if dialect not in {"postgresql", "sqlite"}:
            raise AIUsageUnavailable("AI usage limits unavailable")
        insert = postgres_insert if dialect == "postgresql" else sqlite_insert
        expired = (
            select(AIUsageBucket.bucket_key)
            .where(AIUsageBucket.expires_at < int(now) - 86400)
            .order_by(AIUsageBucket.expires_at, AIUsageBucket.bucket_key).limit(100)
        )
        db.execute(delete(AIUsageBucket).where(AIUsageBucket.bucket_key.in_(expired)))
        # Every caller acquires shared and user buckets in this order.
        for policy in policies:
            expires = int(now) // policy.window_seconds * policy.window_seconds
            expires += policy.window_seconds
            statement = insert(AIUsageBucket).values(
                bucket_key=bucket_key(policy, now), attempts=1, expires_at=expires,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[AIUsageBucket.bucket_key],
                set_={"attempts": AIUsageBucket.attempts + 1},
                where=AIUsageBucket.attempts < policy.limit,
            ).returning(AIUsageBucket.attempts)
            if db.scalar(statement) is None:
                retry = max(1, math.ceil(expires - now))
                if blocked is None or retry > blocked[0]:
                    blocked = (retry, policy.message)
        if blocked:
            db.rollback()
        else:
            db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise AIUsageUnavailable("AI usage limits unavailable") from exc
    if blocked:
        raise AIUsageLimited(*blocked)


def consume_course_generation(db: Session, course_id: uuid.UUID, provider_name: str) -> None:
    if provider_name == "fake":
        return
    owner_id = db.scalar(select(Course.owner_id).where(Course.id == course_id))
    if owner_id is None:
        raise AIUsageUnavailable("AI usage limits unavailable")
    consume_generation(db, owner_id)


def get_ai_usage(db: Session, user_id: uuid.UUID) -> AIUsageResponse:
    now = time.time()
    windows = []
    try:
        for policy in user_budgets(user_id):
            used = db.scalar(select(AIUsageBucket.attempts).where(
                AIUsageBucket.bucket_key == bucket_key(policy, now)
            )) or 0
            expires = int(now) // policy.window_seconds * policy.window_seconds
            expires += policy.window_seconds
            windows.append(AIUsageWindow(
                used=used, limit=policy.limit, remaining=max(0, policy.limit - used),
                resets_at=datetime.fromtimestamp(expires, UTC),
            ))
    except SQLAlchemyError as exc:
        db.rollback()
        raise AIUsageUnavailable("AI usage limits unavailable") from exc
    return AIUsageResponse(
        enabled=settings.llm_provider.strip().lower() != "fake", minute=windows[0], day=windows[1],
    )
