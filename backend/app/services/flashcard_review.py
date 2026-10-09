import math
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, selectinload

from app.models import Course, Flashcard, FlashcardProgress, FlashcardSet
from app.schemas.flashcard import FlashcardCitationResponse
from app.schemas.flashcard_review import (
    DueFlashcard,
    FlashcardReviewCreate,
    FlashcardReviewQueue,
    FlashcardReviewResponse,
    ReviewRating,
)


class ReviewConflict(ValueError):
    pass


class ReviewCardNotFound(ValueError):
    pass


def next_interval(rating: ReviewRating, previous: int = 0) -> int:
    """Simple deterministic schedule in minutes; not an FSRS/SM-2 implementation."""
    if rating == ReviewRating.again:
        return 10
    minimum, multiplier = {
        ReviewRating.hard: (1440, 1.2),
        ReviewRating.good: (4320, 2),
        ReviewRating.easy: (10080, 3),
    }[rating]
    return min(525600, max(minimum, math.ceil(previous * multiplier)))


def timestamp(value: int) -> datetime:
    return datetime.fromtimestamp(value, UTC)


def get_review_queue(
    db: Session, course_id: uuid.UUID, user_id: uuid.UUID, limit: int = 20,
) -> FlashcardReviewQueue:
    now = int(time.time())
    progress = FlashcardProgress
    base = (
        select(Flashcard, progress)
        .join(FlashcardSet, Flashcard.flashcard_set_id == FlashcardSet.id)
        .join(Course, FlashcardSet.course_id == Course.id)
        .outerjoin(progress, and_(progress.flashcard_id == Flashcard.id,
                                 progress.user_id == user_id))
        .where(Course.id == course_id, Course.owner_id == user_id)
    )
    counts = db.execute(base.with_only_columns(
        func.count(Flashcard.id), func.count(progress.flashcard_id),
    )).one()
    due = or_(progress.flashcard_id.is_(None), progress.due_at <= now)
    due_count = db.scalar(base.with_only_columns(func.count(Flashcard.id)).where(due)) or 0
    next_due = db.scalar(base.with_only_columns(func.min(progress.due_at))
                         .where(progress.due_at > now))
    rows = db.execute(
        base.where(due).options(selectinload(Flashcard.citations),
                                selectinload(Flashcard.flashcard_set))
        .order_by(func.coalesce(progress.due_at, now), Flashcard.created_at, Flashcard.id)
        .limit(limit)
    ).all()
    return FlashcardReviewQueue(
        total_count=counts[0], reviewed_count=counts[1], due_count=due_count,
        next_due_at=timestamp(next_due) if next_due is not None else None,
        cards=[DueFlashcard(
            id=card.id, flashcard_set_id=card.flashcard_set_id,
            title=card.flashcard_set.title or card.flashcard_set.topic,
            front=card.front, back=card.back,
            version=saved.review_count if saved else 0,
            due_at=timestamp(saved.due_at) if saved else None,
            citations=[FlashcardCitationResponse.model_validate(c) for c in card.citations],
        ) for card, saved in rows],
    )


def review_flashcard(
    db: Session, card_id: uuid.UUID, user_id: uuid.UUID, payload: FlashcardReviewCreate,
) -> FlashcardReviewResponse:
    now = int(time.time())
    card = db.scalar(select(Flashcard).join(FlashcardSet).join(Course).where(
        Flashcard.id == card_id, Course.owner_id == user_id,
    ))
    if card is None:
        raise ReviewCardNotFound("Flashcard was not found")
    previous = db.get(FlashcardProgress, (card_id, user_id))
    if payload.version != (previous.review_count if previous else 0):
        raise ReviewConflict("This card's progress changed. Refresh due cards to continue.")
    if previous and previous.due_at > now:
        raise ReviewConflict("This card is not due yet. Refresh due cards to continue.")
    interval = next_interval(payload.rating, previous.interval_minutes if previous else 0)
    values = dict(
        flashcard_id=card_id, user_id=user_id, review_count=payload.version + 1,
        interval_minutes=interval, last_rating=payload.rating.value,
        last_reviewed_at=now, due_at=now + interval * 60,
    )
    insert = postgres_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(FlashcardProgress).values(**values)
    statement = statement.on_conflict_do_update(
        index_elements=[FlashcardProgress.flashcard_id, FlashcardProgress.user_id],
        set_={key: value for key, value in values.items()
              if key not in {"flashcard_id", "user_id"}},
        where=and_(FlashcardProgress.review_count == payload.version,
                   FlashcardProgress.due_at <= now),
    ).returning(FlashcardProgress.review_count)
    if db.scalar(statement) is None:
        db.rollback()
        raise ReviewConflict("This card's progress changed. Refresh due cards to continue.")
    db.commit()
    return FlashcardReviewResponse(
        flashcard_id=card_id, version=payload.version + 1, rating=payload.rating,
        interval_minutes=interval, reviewed_at=timestamp(now),
        due_at=timestamp(values["due_at"]),
    )
