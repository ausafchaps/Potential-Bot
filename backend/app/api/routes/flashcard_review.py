import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import CurrentUser, Database
from app.schemas.flashcard_review import (
    FlashcardReviewCreate,
    FlashcardReviewQueue,
    FlashcardReviewResponse,
)
from app.services.flashcard_review import (
    ReviewCardNotFound,
    ReviewConflict,
    get_review_queue,
    review_flashcard,
)

router = APIRouter(tags=["flashcard review"])


@router.get("/courses/{course_id}/flashcard-review", response_model=FlashcardReviewQueue)
def review_queue_endpoint(
    course_id: uuid.UUID, user: CurrentUser, db: Database, response: Response,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> FlashcardReviewQueue:
    response.headers["Cache-Control"] = "no-store"
    try:
        return get_review_queue(db, course_id, user.id, limit)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Flashcard review is temporarily unavailable") from exc


@router.post("/flashcards/{flashcard_id}/reviews", response_model=FlashcardReviewResponse)
def review_card_endpoint(
    flashcard_id: uuid.UUID, payload: FlashcardReviewCreate,
    user: CurrentUser, db: Database, response: Response,
) -> FlashcardReviewResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        return review_flashcard(db, flashcard_id, user.id, payload)
    except ReviewCardNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except ReviewConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Flashcard review is temporarily unavailable") from exc
