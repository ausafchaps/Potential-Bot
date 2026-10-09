import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    Answer,
    AuthSession,
    Course,
    Document,
    Flashcard,
    FlashcardSet,
    Question,
    Quiz,
    QuizAttempt,
    User,
)
from app.services.auth import hash_token

bearer = HTTPBearer(auto_error=False)
Database = Annotated[Session, Depends(get_db)]


def unauthorized() -> HTTPException:
    return HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})


def get_current_session(
    db: Database,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthSession:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    if len(credentials.credentials) > 256:
        raise unauthorized()
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(credentials.credentials),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    if session is None:
        raise unauthorized()
    return session


def get_current_user(
    db: Database,
    session: Annotated[AuthSession, Depends(get_current_session)],
) -> User:
    user = db.get(User, session.user_id)
    if user is None:
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> None:
    if not user.is_admin:
        raise HTTPException(403, "Administrator access required")


def require_resource_owner(request: Request, db: Database, user: CurrentUser) -> None:
    """Resolve ownership through persisted parents, including direct resource URLs.

    This dependency is attached to every private router. Unknown resource paths
    fail closed so adding an endpoint cannot silently bypass ownership checks.
    """
    resources = {
        "user_id": (User, "User"),
        "course_id": (Course, "Course"),
        "document_id": (Document, "Document"),
        "question_id": (Question, "Question"),
        "answer_id": (Answer, "Answer"),
        "quiz_id": (Quiz, "Quiz"),
        "attempt_id": (QuizAttempt, "Quiz attempt"),
        "flashcard_set_id": (FlashcardSet, "Flashcard set"),
        "flashcard_id": (Flashcard, "Flashcard"),
    }
    checked = False
    for parameter, (model, label) in resources.items():
        if parameter not in request.path_params:
            continue
        try:
            resource_id = uuid.UUID(str(request.path_params[parameter]))
        except ValueError as exc:
            raise HTTPException(422, "Invalid resource ID") from exc
        resource = db.get(model, resource_id)
        if resource is None:
            raise HTTPException(404, f"{label} was not found")
        if isinstance(resource, User):
            owner_id = resource.id
        else:
            if isinstance(resource, Answer):
                course_id = resource.question.course_id
            elif isinstance(resource, QuizAttempt):
                course_id = resource.quiz.course_id
            elif isinstance(resource, Flashcard):
                course_id = resource.flashcard_set.course_id
            elif isinstance(resource, Course):
                course_id = resource.id
            else:
                course_id = resource.course_id
            course = db.get(Course, course_id)
            owner_id = course.owner_id if course else None
        if owner_id != user.id:
            raise HTTPException(404, f"{label} was not found")
        checked = True
    if not checked:
        raise HTTPException(403, "Resource access is not configured")
