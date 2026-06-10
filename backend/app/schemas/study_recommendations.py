import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class StudyRecommendationPriority(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"
    mastered = "mastered"


class StudyRecommendationActionResponse(BaseModel):
    type: str
    label: str
    description: str
    prompt: str | None = None
    quiz_topic: str | None = None


class StudyRecommendationResponse(BaseModel):
    topic: str
    priority: StudyRecommendationPriority
    reason: str
    attempt_count: int
    question_count: int
    incorrect_count: int
    accuracy_rate: float
    weakness_score: float
    last_attempted_at: datetime
    recommended_actions: list[StudyRecommendationActionResponse]


class StudyRecommendationsResponse(BaseModel):
    course_id: uuid.UUID
    source_topic_count: int
    recommendation_count: int
    recommendations: list[StudyRecommendationResponse]
