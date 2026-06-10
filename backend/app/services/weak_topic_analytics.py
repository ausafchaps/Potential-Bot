import uuid

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models import Course, Quiz, QuizAttempt
from app.schemas.weak_topics import WeakTopicAnalyticsResponse, WeakTopicResponse
from app.services.retrieval import CourseNotFoundError


def get_course_weak_topic_analytics(
    db: Session,
    *,
    course_id: uuid.UUID,
    limit: int = 10,
    min_attempts: int = 1,
) -> WeakTopicAnalyticsResponse:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if min_attempts <= 0:
        raise ValueError("min_attempts must be greater than zero")
    if db.get(Course, course_id) is None:
        raise CourseNotFoundError("Course was not found")

    topic_rows = list(
        db.execute(
            select(
                Quiz.topic.label("topic"),
                func.count(distinct(QuizAttempt.id)).label("attempt_count"),
                func.sum(QuizAttempt.correct_count).label("correct_count"),
                func.sum(QuizAttempt.question_count).label("question_count"),
                func.avg(QuizAttempt.score_percent).label("average_score_percent"),
                func.max(QuizAttempt.created_at).label("last_attempted_at"),
            )
            .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
            .where(Quiz.course_id == course_id)
            .group_by(Quiz.topic)
        )
    )

    weak_topics: list[WeakTopicResponse] = []
    total_attempts = 0
    total_questions = 0
    for row in topic_rows:
        attempt_count = int(row.attempt_count or 0)
        question_count = int(row.question_count or 0)
        correct_count = int(row.correct_count or 0)
        total_attempts += attempt_count
        total_questions += question_count

        if attempt_count < min_attempts or question_count == 0:
            continue

        incorrect_count = question_count - correct_count
        accuracy_rate = correct_count / question_count
        weakness_score = incorrect_count / question_count
        weak_topics.append(
            WeakTopicResponse(
                topic=row.topic,
                attempt_count=attempt_count,
                question_count=question_count,
                correct_count=correct_count,
                incorrect_count=incorrect_count,
                accuracy_rate=round(accuracy_rate, 2),
                weakness_score=round(weakness_score, 2),
                average_score_percent=round(float(row.average_score_percent or 0.0), 2),
                last_attempted_at=row.last_attempted_at,
            )
        )

    weak_topics.sort(
        key=lambda topic: (
            -topic.weakness_score,
            -topic.question_count,
            topic.topic.lower(),
        )
    )

    return WeakTopicAnalyticsResponse(
        course_id=course_id,
        topic_count=len(topic_rows),
        attempt_count=total_attempts,
        question_count=total_questions,
        weak_topics=weak_topics[:limit],
    )
