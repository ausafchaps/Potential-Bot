import uuid

from sqlalchemy.orm import Session

from app.schemas.study_recommendations import (
    StudyRecommendationActionResponse,
    StudyRecommendationPriority,
    StudyRecommendationResponse,
    StudyRecommendationsResponse,
)
from app.schemas.weak_topics import WeakTopicResponse
from app.services.weak_topic_analytics import get_course_weak_topic_analytics


def get_course_study_recommendations(
    db: Session,
    *,
    course_id: uuid.UUID,
    limit: int = 5,
    min_attempts: int = 1,
    include_mastered: bool = False,
) -> StudyRecommendationsResponse:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if min_attempts <= 0:
        raise ValueError("min_attempts must be greater than zero")

    analytics = get_course_weak_topic_analytics(
        db,
        course_id=course_id,
        limit=50,
        min_attempts=min_attempts,
    )
    recommendations = [
        build_topic_recommendation(topic)
        for topic in analytics.weak_topics
        if include_mastered or topic.weakness_score > 0
    ]

    return StudyRecommendationsResponse(
        course_id=course_id,
        source_topic_count=analytics.topic_count,
        recommendation_count=len(recommendations[:limit]),
        recommendations=recommendations[:limit],
    )


def build_topic_recommendation(topic: WeakTopicResponse) -> StudyRecommendationResponse:
    priority = classify_priority(topic.weakness_score)
    return StudyRecommendationResponse(
        topic=topic.topic,
        priority=priority,
        reason=build_reason(topic),
        attempt_count=topic.attempt_count,
        question_count=topic.question_count,
        incorrect_count=topic.incorrect_count,
        accuracy_rate=topic.accuracy_rate,
        weakness_score=topic.weakness_score,
        last_attempted_at=topic.last_attempted_at,
        recommended_actions=build_actions(topic, priority),
    )


def classify_priority(weakness_score: float) -> StudyRecommendationPriority:
    if weakness_score >= 0.75:
        return StudyRecommendationPriority.high
    if weakness_score >= 0.4:
        return StudyRecommendationPriority.medium
    if weakness_score > 0:
        return StudyRecommendationPriority.low
    return StudyRecommendationPriority.mastered


def build_reason(topic: WeakTopicResponse) -> str:
    accuracy_percent = round(topic.accuracy_rate * 100)
    return (
        f"Accuracy is {accuracy_percent}% across "
        f"{topic.question_count} attempted questions."
    )


def build_actions(
    topic: WeakTopicResponse,
    priority: StudyRecommendationPriority,
) -> list[StudyRecommendationActionResponse]:
    if priority == StudyRecommendationPriority.mastered:
        return [
            StudyRecommendationActionResponse(
                type="maintain_topic",
                label=f"Keep {topic.topic} warm",
                description="Review this topic later to maintain retention.",
                quiz_topic=topic.topic,
            )
        ]

    actions = [
        StudyRecommendationActionResponse(
            type="review_topic",
            label=f"Review {topic.topic}",
            description="Ask for a grounded explanation using the uploaded course material.",
            prompt=f"Explain {topic.topic} using my course notes and cite the sources.",
        )
    ]

    if topic.incorrect_count > 0:
        actions.append(
            StudyRecommendationActionResponse(
                type="practice_missed_questions",
                label="Practice missed questions",
                description="Review the questions answered incorrectly for this topic.",
            )
        )

    actions.append(
        StudyRecommendationActionResponse(
            type="generate_quiz",
            label="Generate another quiz",
            description="Create a fresh quiz for another practice attempt.",
            quiz_topic=topic.topic,
        )
    )
    return actions
