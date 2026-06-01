import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Answer, Course, Question


class CourseNotFoundError(ValueError):
    pass


class QuestionNotFoundError(ValueError):
    pass


class AnswerNotFoundError(ValueError):
    pass


def list_course_questions(db: Session, course_id: uuid.UUID) -> list[Question]:
    course = db.get(Course, course_id)
    if course is None:
        raise CourseNotFoundError("Course was not found")

    statement = (
        select(Question)
        .options(selectinload(Question.answers))
        .where(Question.course_id == course_id)
        .order_by(Question.created_at.desc(), Question.id.desc())
    )
    return list(db.scalars(statement))


def get_question_detail(db: Session, question_id: uuid.UUID) -> Question:
    statement = (
        select(Question)
        .options(
            selectinload(Question.answers).selectinload(Answer.citations),
            selectinload(Question.answers).selectinload(Answer.feedback_events),
        )
        .where(Question.id == question_id)
    )
    question = db.scalar(statement)
    if question is None:
        raise QuestionNotFoundError("Question was not found")
    return question


def get_answer_detail(db: Session, answer_id: uuid.UUID) -> Answer:
    statement = (
        select(Answer)
        .options(
            selectinload(Answer.citations),
            selectinload(Answer.feedback_events),
        )
        .where(Answer.id == answer_id)
    )
    answer = db.scalar(statement)
    if answer is None:
        raise AnswerNotFoundError("Answer was not found")
    return answer


def calculate_average_rating(answer: Answer) -> float | None:
    if not answer.feedback_events:
        return None

    total = sum(feedback.rating for feedback in answer.feedback_events)
    return round(total / len(answer.feedback_events), 2)
