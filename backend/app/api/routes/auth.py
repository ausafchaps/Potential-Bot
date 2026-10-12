from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from app.api.auth_rate_limit import limit_login_email, limit_login_ip, limit_signup
from app.api.dependencies import CurrentUser, Database, get_current_session
from app.api.routes.account_recovery import auto_verification
from app.models import AuthSession, User
from app.schemas.ai_usage import AIUsageResponse
from app.schemas.auth import LoginRequest, SessionResponse
from app.schemas.storage import StorageUsage
from app.schemas.user import UserCreate, UserResponse
from app.services.ai_usage import get_ai_usage
from app.services.auth import CredentialsChanged, authenticate, create_session
from app.services.storage import get_storage_usage
from app.services.user_course import DuplicateUserEmailError, create_user

router = APIRouter(prefix="/auth", tags=["authentication"])


def session_response(db: Database, user, response: Response) -> SessionResponse:
    try:
        token, session = create_session(db, user)
    except CredentialsChanged as exc:
        raise HTTPException(401, "Invalid email or password") from exc
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        access_token=token,
        expires_at=session.expires_at.replace(tzinfo=UTC),
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=SessionResponse, status_code=201,
             dependencies=[Depends(limit_signup)])
def register(payload: UserCreate, db: Database, response: Response, request: Request,
             tasks: BackgroundTasks) -> SessionResponse:
    try:
        user = create_user(db, payload)
    except DuplicateUserEmailError as exc:
        raise HTTPException(409, str(exc)) from exc
    session = session_response(db, user, response)
    auto_verification(db, user, request, tasks)
    return session


@router.post("/login", response_model=SessionResponse,
             dependencies=[Depends(limit_login_ip)])
def login(payload: LoginRequest, db: Database, response: Response) -> SessionResponse:
    limit_login_email(db, payload.email)
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


@router.get("/ai-usage", response_model=AIUsageResponse)
def ai_usage(db: Database, user: CurrentUser, response: Response) -> AIUsageResponse:
    response.headers["Cache-Control"] = "no-store"
    return get_ai_usage(db, user.id)


@router.get("/storage-usage", response_model=StorageUsage)
def storage_usage(db: Database, user: CurrentUser, response: Response) -> StorageUsage:
    response.headers["Cache-Control"] = "no-store"
    return get_storage_usage(db, user.id)
