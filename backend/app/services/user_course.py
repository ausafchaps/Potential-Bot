import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, User
from app.schemas.course import CourseCreate
from app.schemas.user import UserCreate


class DuplicateUserEmailError(ValueError):
    pass


class UserNotFoundError(ValueError):
    pass


class CourseNotFoundError(ValueError):
    pass


def create_user(db: Session, payload: UserCreate) -> User:
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        raise DuplicateUserEmailError("A user with this email already exists")

    user = User(email=payload.email, display_name=payload.display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError("User was not found")
    return user


def create_course_for_user(db: Session, user_id: uuid.UUID, payload: CourseCreate) -> Course:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError("User was not found")

    course = Course(
        owner_id=user.id,
        title=payload.title,
        description=payload.description,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def list_courses_for_user(db: Session, user_id: uuid.UUID) -> list[Course]:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError("User was not found")

    statement = select(Course).where(Course.owner_id == user_id).order_by(Course.created_at)
    return list(db.scalars(statement))


def get_course(db: Session, course_id: uuid.UUID) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise CourseNotFoundError("Course was not found")
    return course
