import uuid
from datetime import datetime

from pydantic import BaseModel


class WeakTopicResponse(BaseModel):
    topic: str
    attempt_count: int
    question_count: int
    correct_count: int
    incorrect_count: int
    accuracy_rate: float
    weakness_score: float
    average_score_percent: float
    last_attempted_at: datetime


class WeakTopicAnalyticsResponse(BaseModel):
    course_id: uuid.UUID
    topic_count: int
    attempt_count: int
    question_count: int
    weak_topics: list[WeakTopicResponse]
