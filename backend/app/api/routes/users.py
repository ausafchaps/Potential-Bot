import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.course import CourseCreate, CourseResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.user_course import (
    DuplicateUserEmailError,
    UserNotFoundError,
    create_course_for_user,
    create_user,
    get_user,
    list_courses_for_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    try:
        return create_user(db, payload)
    except DuplicateUserEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{user_id}", response_model=UserResponse)
def get_user_endpoint(
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    try:
        return get_user(db, user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{user_id}/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_course_endpoint(
    user_id: uuid.UUID,
    payload: CourseCreate,
    db: Annotated[Session, Depends(get_db)],
) -> CourseResponse:
    try:
        return create_course_for_user(db, user_id, payload)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{user_id}/courses", response_model=list[CourseResponse])
def list_courses_endpoint(
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[CourseResponse]:
    try:
        return list_courses_for_user(db, user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
