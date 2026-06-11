import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.study_recommendations import StudyRecommendationsResponse
from app.services.retrieval import CourseNotFoundError
from app.services.study_recommendations import get_course_study_recommendations

router = APIRouter(tags=["study recommendations"])


@router.get(
    "/courses/{course_id}/study-recommendations",
    response_model=StudyRecommendationsResponse,
)
def get_course_study_recommendations_endpoint(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
    min_attempts: Annotated[int, Query(ge=1, le=100)] = 1,
    include_mastered: bool = False,
) -> StudyRecommendationsResponse:
    try:
        return get_course_study_recommendations(
            db,
            course_id=course_id,
            limit=limit,
            min_attempts=min_attempts,
            include_mastered=include_mastered,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
