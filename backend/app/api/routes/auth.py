from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.dependencies import CurrentUser, Database, get_current_session
from app.models import AuthSession, User
from app.schemas.auth import LoginRequest, SessionResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.auth import authenticate, create_session
from app.services.user_course import DuplicateUserEmailError, create_user

router = APIRouter(prefix="/auth", tags=["authentication"])


def session_response(db: Database, user, response: Response) -> SessionResponse:
    token, session = create_session(db, user)
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        access_token=token,
        expires_at=session.expires_at.replace(tzinfo=UTC),
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=SessionResponse, status_code=201)
def register(payload: UserCreate, db: Database, response: Response) -> SessionResponse:
    try:
        user = create_user(db, payload)
    except DuplicateUserEmailError as exc:
        raise HTTPException(409, str(exc)) from exc
    return session_response(db, user, response)


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, db: Database, response: Response) -> SessionResponse:
    user = authenticate(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            401, "Invalid email or password", headers={"WWW-Authenticate": "Bearer"}
        )
    return session_response(db, user, response)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser, response: Response) -> User:
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/logout", status_code=204)
def logout(db: Database, session: Annotated[AuthSession, Depends(get_current_session)]) -> None:
    db.delete(session)
    db.commit()
