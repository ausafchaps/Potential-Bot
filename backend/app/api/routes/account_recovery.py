import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth_rate_limit import client_identity, enforce
from app.api.dependencies import CurrentUser, Database
from app.core.config import settings
from app.models import User
from app.schemas.account_recovery import (
    AuthCapabilities,
    LinkToken,
    RecoveryEmail,
    RecoveryMessage,
    ResetPassword,
)
from app.services import account_email
from app.services.account_recovery import InvalidAccountLink, consume_link, issue_link
from app.services.auth_rate_limit import AttemptLimit

router = APIRouter(prefix="/auth", tags=["account recovery"])
logger = logging.getLogger(__name__)


def unavailable() -> HTTPException:
    return HTTPException(503, "Account emails are not available. Please contact the app owner.",
                         headers={"Cache-Control": "no-store"})


def limit_email(request: Request, db: Database, email: str) -> None:
    enforce(db, [
        AttemptLimit("account-email-ip", client_identity(request),
                     settings.auth_email_ip_limit, 3600),
        AttemptLimit("account-email-address", email, settings.auth_email_address_limit, 3600),
        AttemptLimit("account-email-project", "project", settings.auth_email_project_daily_limit,
                     86400),
    ])


def enqueue_email(db: Database, user: User, purpose: str, tasks: BackgroundTasks) -> None:
    link = issue_link(db, user, purpose)
    tasks.add_task(account_email.send_account_email, user.email, purpose, link)


def auto_verification(db: Database, user: User, request: Request, tasks: BackgroundTasks) -> None:
    if not account_email.email_enabled():
        return
    try:
        limit_email(request, db, user.email)
        enqueue_email(db, user, "verify", tasks)
    except (HTTPException, SQLAlchemyError):
        db.rollback()
        logger.warning("Signup verification email could not be queued; request it again")


@router.get("/capabilities", response_model=AuthCapabilities)
def capabilities(response: Response) -> AuthCapabilities:
    response.headers["Cache-Control"] = "no-store"
    return AuthCapabilities(account_email_enabled=account_email.email_enabled(),
                            verification_required=settings.auth_require_email_verification)


@router.post("/forgot-password", response_model=RecoveryMessage, status_code=202)
def forgot_password(payload: RecoveryEmail, db: Database, request: Request,
                    response: Response, tasks: BackgroundTasks) -> RecoveryMessage:
    response.headers["Cache-Control"] = "no-store"
    if not account_email.email_enabled():
        raise unavailable()
    limit_email(request, db, payload.email)
    try:
        user = db.scalar(select(User).where(User.email == payload.email))
        if user and user.password_hash:
            enqueue_email(db, user, "reset", tasks)
    except SQLAlchemyError as exc:
        db.rollback()
        raise unavailable() from exc
    return RecoveryMessage(
        message="If an eligible account exists, a password reset link will be emailed."
    )


@router.post("/resend-verification", response_model=RecoveryMessage, status_code=202)
def resend_verification(user: CurrentUser, db: Database, request: Request,
                        response: Response, tasks: BackgroundTasks) -> RecoveryMessage:
    response.headers["Cache-Control"] = "no-store"
    if not account_email.email_enabled():
        raise unavailable()
    limit_email(request, db, user.email)
    if user.email_verified:
        return RecoveryMessage(message="Your email is already verified.")
    try:
        enqueue_email(db, user, "verify", tasks)
    except SQLAlchemyError as exc:
        db.rollback()
        raise unavailable() from exc
    return RecoveryMessage(message="Verification requested. Check your inbox for the link.")


def limit_link(request: Request, db: Database) -> None:
    enforce(db, [AttemptLimit("account-link-ip", client_identity(request), 30, 900)])


@router.post("/reset-password", response_model=RecoveryMessage)
def reset_password(payload: ResetPassword, db: Database, request: Request,
                   response: Response) -> RecoveryMessage:
    response.headers["Cache-Control"] = "no-store"
    limit_link(request, db)
    try:
        consume_link(db, payload.token, "reset", payload.password)
    except InvalidAccountLink as exc:
        raise HTTPException(400, str(exc), headers={"Cache-Control": "no-store"}) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise unavailable() from exc
    return RecoveryMessage(message="Password reset. Sign in with your new password.")


@router.post("/verify-email", response_model=RecoveryMessage)
def verify_email(payload: LinkToken, db: Database, request: Request,
                 response: Response) -> RecoveryMessage:
    response.headers["Cache-Control"] = "no-store"
    limit_link(request, db)
    try:
        consume_link(db, payload.token, "verify")
    except InvalidAccountLink as exc:
        raise HTTPException(400, str(exc), headers={"Cache-Control": "no-store"}) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise unavailable() from exc
    return RecoveryMessage(message="Email verified. You can sign in to your study workspace.")
