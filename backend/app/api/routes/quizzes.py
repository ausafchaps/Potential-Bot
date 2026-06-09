import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Quiz
from app.schemas.quiz import (
    QuizCitationResponse,
    QuizCreate,
    QuizQuestionResponse,
    QuizResponse,
    QuizSummaryResponse,
)
from app.services.llm.base import LLMProviderConfigurationError, LLMProviderError
from app.services.quiz_generation import (
    QuizGenerationError,
    QuizNotFoundError,
    create_course_quiz,
    get_quiz,
    list_course_quizzes,
)
from app.services.retrieval import CourseNotFoundError, EmptySearchQueryError

router = APIRouter(tags=["quizzes"])


def build_quiz_response(quiz: Quiz) -> QuizResponse:
    return QuizResponse(
        id=quiz.id,
        course_id=quiz.course_id,
        topic=quiz.topic,
        title=quiz.title,
        difficulty=quiz.difficulty,
        status=quiz.status,
        provider=quiz.provider,
        questions=[
            QuizQuestionResponse(
                id=question.id,
                position=question.position,
                question=question.question_text,
                explanation=question.explanation,
                options=question.options,
                citations=[
                    QuizCitationResponse.model_validate(citation)
                    for citation in question.citations
                ],
            )
            for question in quiz.questions
        ],
        created_at=quiz.created_at,
        updated_at=quiz.updated_at,
    )


def build_quiz_summary_response(quiz: Quiz) -> QuizSummaryResponse:
    return QuizSummaryResponse(
        id=quiz.id,
        course_id=quiz.course_id,
        topic=quiz.topic,
        title=quiz.title,
        difficulty=quiz.difficulty,
        status=quiz.status,
        provider=quiz.provider,
        question_count=len(quiz.questions),
        created_at=quiz.created_at,
        updated_at=quiz.updated_at,
    )


@router.post(
    "/courses/{course_id}/quizzes",
    response_model=QuizResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_course_quiz_endpoint(
    course_id: uuid.UUID,
    payload: QuizCreate,
    db: Annotated[Session, Depends(get_db)],
) -> QuizResponse:
    try:
        quiz = create_course_quiz(db, course_id=course_id, payload=payload)
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
    except QuizGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return build_quiz_response(quiz)


@router.get("/courses/{course_id}/quizzes", response_model=list[QuizSummaryResponse])
def list_course_quizzes_endpoint(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[QuizSummaryResponse]:
    try:
        quizzes = list_course_quizzes(db, course_id)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [build_quiz_summary_response(quiz) for quiz in quizzes]


@router.get("/quizzes/{quiz_id}", response_model=QuizResponse)
def get_quiz_endpoint(
    quiz_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> QuizResponse:
    try:
        quiz = get_quiz(db, quiz_id)
    except QuizNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return build_quiz_response(quiz)
