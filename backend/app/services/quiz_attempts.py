import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Quiz,
    QuizAttempt,
    QuizAttemptAnswer,
    QuizQuestion,
    QuizQuestionOption,
    QuizStatus,
)
from app.schemas.quiz import QuizAttemptCreate
from app.services.quiz_generation import QuizNotFoundError


class QuizAttemptNotFoundError(ValueError):
    pass


class QuizAttemptValidationError(ValueError):
    pass


def submit_quiz_attempt(
    db: Session,
    *,
    quiz_id: uuid.UUID,
    payload: QuizAttemptCreate,
) -> QuizAttempt:
    quiz = get_generated_quiz_for_attempt(db, quiz_id)
    selected_options_by_question_id = normalize_attempt_answers(payload)

    quiz_question_ids = {question.id for question in quiz.questions}
    if set(selected_options_by_question_id) != quiz_question_ids:
        raise QuizAttemptValidationError("Attempt must answer every quiz question exactly once")

    attempt_answers: list[QuizAttemptAnswer] = []
    correct_count = 0
    for question in quiz.questions:
        selected_option_id = selected_options_by_question_id[question.id]
        selected_option = find_question_option(question, selected_option_id)
        correct_option = find_correct_option(question)
        is_correct = selected_option.id == correct_option.id
        if is_correct:
            correct_count += 1

        attempt_answers.append(
            QuizAttemptAnswer(
                question_id=question.id,
                selected_option_id=selected_option.id,
                question_position=question.position,
                question_text=question.question_text,
                selected_option_text=selected_option.text,
                correct_option_id=correct_option.id,
                correct_option_text=correct_option.text,
                is_correct=is_correct,
            )
        )

    question_count = len(quiz.questions)
    score_percent = round((correct_count / question_count) * 100, 2)
    attempt = QuizAttempt(
        quiz_id=quiz.id,
        correct_count=correct_count,
        question_count=question_count,
        score_percent=score_percent,
        answers=attempt_answers,
    )
    db.add(attempt)
    db.commit()
    return get_quiz_attempt(db, attempt.id)


def get_generated_quiz_for_attempt(db: Session, quiz_id: uuid.UUID) -> Quiz:
    quiz = db.scalar(
        select(Quiz)
        .where(Quiz.id == quiz_id)
        .options(selectinload(Quiz.questions).selectinload(QuizQuestion.options))
    )
    if quiz is None:
        raise QuizNotFoundError("Quiz was not found")
    if quiz.status != QuizStatus.generated:
        raise QuizAttemptValidationError("Cannot submit an attempt for a quiz without questions")
    if not quiz.questions:
        raise QuizAttemptValidationError("Cannot submit an attempt for a quiz without questions")
    return quiz


def normalize_attempt_answers(payload: QuizAttemptCreate) -> dict[uuid.UUID, uuid.UUID]:
    answers_by_question_id: dict[uuid.UUID, uuid.UUID] = {}
    for answer in payload.answers:
        if answer.question_id in answers_by_question_id:
            raise QuizAttemptValidationError("Attempt includes duplicate answers for a question")
        answers_by_question_id[answer.question_id] = answer.selected_option_id
    return answers_by_question_id


def find_question_option(
    question: QuizQuestion,
    selected_option_id: uuid.UUID,
) -> QuizQuestionOption:
    for option in question.options:
        if option.id == selected_option_id:
            return option
    raise QuizAttemptValidationError("Selected option does not belong to the quiz question")


def find_correct_option(question: QuizQuestion) -> QuizQuestionOption:
    correct_options = [option for option in question.options if option.is_correct]
    if len(correct_options) != 1:
        raise QuizAttemptValidationError("Quiz question does not have exactly one correct option")
    return correct_options[0]


def list_quiz_attempts(db: Session, quiz_id: uuid.UUID) -> list[QuizAttempt]:
    if db.get(Quiz, quiz_id) is None:
        raise QuizNotFoundError("Quiz was not found")

    return list(
        db.scalars(
            select(QuizAttempt)
            .where(QuizAttempt.quiz_id == quiz_id)
            .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id.desc())
        )
    )


def get_quiz_attempt(db: Session, attempt_id: uuid.UUID) -> QuizAttempt:
    attempt = db.scalar(
        select(QuizAttempt)
        .where(QuizAttempt.id == attempt_id)
        .options(selectinload(QuizAttempt.answers))
    )
    if attempt is None:
        raise QuizAttemptNotFoundError("Quiz attempt was not found")
    return attempt
