import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import FlashcardSet
from app.schemas.flashcard import (
    FlashcardCitationResponse,
    FlashcardResponse,
    FlashcardSetCreate,
    FlashcardSetResponse,
    FlashcardSetSummaryResponse,
)
from app.services.flashcard_generation import (
    FlashcardGenerationError,
    FlashcardSetNotFoundError,
    create_course_flashcard_set,
    get_flashcard_set,
    list_course_flashcard_sets,
)
from app.services.llm.base import LLMProviderConfigurationError, LLMProviderError
from app.services.retrieval import CourseNotFoundError, EmptySearchQueryError

router = APIRouter(tags=["flashcards"])


def build_flashcard_set_response(flashcard_set: FlashcardSet) -> FlashcardSetResponse:
    return FlashcardSetResponse(
        id=flashcard_set.id,
        course_id=flashcard_set.course_id,
        topic=flashcard_set.topic,
        title=flashcard_set.title,
        difficulty=flashcard_set.difficulty,
        status=flashcard_set.status,
        provider=flashcard_set.provider,
        cards=[
            FlashcardResponse(
                id=card.id,
                position=card.position,
                front=card.front,
                back=card.back,
                citations=[
                    FlashcardCitationResponse.model_validate(citation)
                    for citation in card.citations
                ],
            )
            for card in flashcard_set.cards
        ],
        created_at=flashcard_set.created_at,
        updated_at=flashcard_set.updated_at,
    )


def build_flashcard_set_summary_response(
    flashcard_set: FlashcardSet,
) -> FlashcardSetSummaryResponse:
    return FlashcardSetSummaryResponse(
        id=flashcard_set.id,
        course_id=flashcard_set.course_id,
        topic=flashcard_set.topic,
        title=flashcard_set.title,
        difficulty=flashcard_set.difficulty,
        status=flashcard_set.status,
        provider=flashcard_set.provider,
        card_count=len(flashcard_set.cards),
        created_at=flashcard_set.created_at,
        updated_at=flashcard_set.updated_at,
    )


@router.post(
    "/courses/{course_id}/flashcard-sets",
    response_model=FlashcardSetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_course_flashcard_set_endpoint(
    course_id: uuid.UUID,
    payload: FlashcardSetCreate,
    db: Annotated[Session, Depends(get_db)],
) -> FlashcardSetResponse:
    try:
        flashcard_set = create_course_flashcard_set(
            db,
            course_id=course_id,
            payload=payload,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EmptySearchQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except LLMProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except FlashcardGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return build_flashcard_set_response(flashcard_set)


@router.get(
    "/courses/{course_id}/flashcard-sets",
    response_model=list[FlashcardSetSummaryResponse],
)
def list_course_flashcard_sets_endpoint(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[FlashcardSetSummaryResponse]:
    try:
        flashcard_sets = list_course_flashcard_sets(db, course_id)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [
        build_flashcard_set_summary_response(flashcard_set)
        for flashcard_set in flashcard_sets
    ]


@router.get("/flashcard-sets/{flashcard_set_id}", response_model=FlashcardSetResponse)
def get_flashcard_set_endpoint(
    flashcard_set_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> FlashcardSetResponse:
    try:
        flashcard_set = get_flashcard_set(db, flashcard_set_id)
    except FlashcardSetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return build_flashcard_set_response(flashcard_set)
