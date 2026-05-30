import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.feedback import AnswerFeedbackCreate, AnswerFeedbackResponse
from app.services.answer_feedback import AnswerNotFoundError, create_answer_feedback

router = APIRouter(prefix="/answers", tags=["answers"])


@router.post(
    "/{answer_id}/feedback",
    response_model=AnswerFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_answer_feedback_endpoint(
    answer_id: uuid.UUID,
    payload: AnswerFeedbackCreate,
    db: Annotated[Session, Depends(get_db)],
) -> AnswerFeedbackResponse:
    try:
        return create_answer_feedback(db, answer_id=answer_id, payload=payload)
    except AnswerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

