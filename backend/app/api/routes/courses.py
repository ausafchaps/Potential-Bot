import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.course import CourseResponse
from app.services.user_course import CourseNotFoundError, get_course

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/{course_id}", response_model=CourseResponse)
def get_course_endpoint(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> CourseResponse:
    try:
        return get_course(db, course_id)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

