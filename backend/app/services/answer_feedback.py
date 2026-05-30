import uuid

from sqlalchemy.orm import Session

from app.models import Answer, AnswerFeedback
from app.schemas.feedback import AnswerFeedbackCreate


class AnswerNotFoundError(ValueError):
    pass


def create_answer_feedback(
    db: Session,
    *,
    answer_id: uuid.UUID,
    payload: AnswerFeedbackCreate,
) -> AnswerFeedback:
    answer = db.get(Answer, answer_id)
    if answer is None:
        raise AnswerNotFoundError("Answer was not found")

    feedback = AnswerFeedback(
        answer_id=answer_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback

