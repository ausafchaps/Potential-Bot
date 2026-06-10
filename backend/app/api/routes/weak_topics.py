import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.weak_topics import WeakTopicAnalyticsResponse
from app.services.retrieval import CourseNotFoundError
from app.services.weak_topic_analytics import get_course_weak_topic_analytics

router = APIRouter(tags=["weak topics"])


@router.get(
    "/courses/{course_id}/weak-topics",
    response_model=WeakTopicAnalyticsResponse,
)
def get_course_weak_topics_endpoint(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    min_attempts: Annotated[int, Query(ge=1, le=100)] = 1,
) -> WeakTopicAnalyticsResponse:
    try:
        return get_course_weak_topic_analytics(
            db,
            course_id=course_id,
            limit=limit,
            min_attempts=min_attempts,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
