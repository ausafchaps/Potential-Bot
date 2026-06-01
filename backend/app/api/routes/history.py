import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.history import (
    AnswerDetailResponse,
    AnswerSummaryResponse,
    HistoryCitationResponse,
    HistoryFeedbackResponse,
    QuestionDetailResponse,
    QuestionSummaryResponse,
)
from app.services.answer_history import (
    AnswerNotFoundError,
    CourseNotFoundError,
    QuestionNotFoundError,
    calculate_average_rating,
    get_answer_detail,
    get_question_detail,
    list_course_questions,
)

router = APIRouter(tags=["history"])


def build_answer_summary(answer) -> AnswerSummaryResponse:
    return AnswerSummaryResponse(
        id=answer.id,
        question_id=answer.question_id,
        status=answer.status,
        answer=answer.text,
        provider=answer.provider,
        citation_count=len(answer.citations),
        feedback_count=len(answer.feedback_events),
        average_rating=calculate_average_rating(answer),
        created_at=answer.created_at,
        updated_at=answer.updated_at,
    )


@router.get("/courses/{course_id}/questions", response_model=list[QuestionSummaryResponse])
def list_course_questions_endpoint(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[QuestionSummaryResponse]:
    try:
        questions = list_course_questions(db, course_id)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [
        QuestionSummaryResponse(
            id=question.id,
            course_id=question.course_id,
            text=question.text,
            answer_count=len(question.answers),
            created_at=question.created_at,
        )
        for question in questions
    ]


@router.get("/questions/{question_id}", response_model=QuestionDetailResponse)
def get_question_detail_endpoint(
    question_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> QuestionDetailResponse:
    try:
        question = get_question_detail(db, question_id)
    except QuestionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return QuestionDetailResponse(
        id=question.id,
        course_id=question.course_id,
        text=question.text,
        created_at=question.created_at,
        answers=[build_answer_summary(answer) for answer in question.answers],
    )


@router.get("/answers/{answer_id}", response_model=AnswerDetailResponse)
def get_answer_detail_endpoint(
    answer_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> AnswerDetailResponse:
    try:
        answer = get_answer_detail(db, answer_id)
    except AnswerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return AnswerDetailResponse(
        id=answer.id,
        question_id=answer.question_id,
        status=answer.status,
        answer=answer.text,
        provider=answer.provider,
        prompt=answer.prompt,
        citations=[
            HistoryCitationResponse.model_validate(citation)
            for citation in answer.citations
        ],
        feedback=[
            HistoryFeedbackResponse.model_validate(feedback)
            for feedback in answer.feedback_events
        ],
        created_at=answer.created_at,
        updated_at=answer.updated_at,
    )


@router.get("/answers/{answer_id}/citations", response_model=list[HistoryCitationResponse])
def list_answer_citations_endpoint(
    answer_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[HistoryCitationResponse]:
    try:
        answer = get_answer_detail(db, answer_id)
    except AnswerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [HistoryCitationResponse.model_validate(citation) for citation in answer.citations]


@router.get("/answers/{answer_id}/feedback", response_model=list[HistoryFeedbackResponse])
def list_answer_feedback_endpoint(
    answer_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[HistoryFeedbackResponse]:
    try:
        answer = get_answer_detail(db, answer_id)
    except AnswerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [
        HistoryFeedbackResponse.model_validate(feedback)
        for feedback in answer.feedback_events
    ]

