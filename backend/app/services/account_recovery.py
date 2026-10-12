import secrets
import time
from typing import Literal
from urllib.parse import urlencode

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AccountToken, AuthSession, User
from app.services.auth import hash_password, hash_token


class InvalidAccountLink(ValueError):
    def __init__(self):
        super().__init__("This link is invalid, expired, or already used. Request a new one.")


def issue_link(db: Session, user: User, purpose: Literal["reset", "verify"]) -> str:
    now = int(time.time())
    lifetime = settings.auth_reset_minutes * 60 if purpose == "reset" else (
        settings.auth_verify_hours * 3600
    )
    expired = select(AccountToken.token_hash).where(
        AccountToken.expires_at < now - 86400
    ).order_by(AccountToken.expires_at, AccountToken.token_hash).limit(100)
    db.execute(delete(AccountToken).where(AccountToken.token_hash.in_(expired)))
    token = secrets.token_urlsafe(32)
    db.add(AccountToken(
        token_hash=hash_token(token), user_id=user.id, purpose=purpose,
        email_hash=hash_token(user.email), credential_version=user.credential_version,
        expires_at=now + lifetime,
    ))
    db.commit()
    # Fragment tokens stay out of HTTP access logs and referrer headers.
    return f"{settings.public_app_url.rstrip('/')}/#{urlencode({purpose: token})}"


def consume_link(db: Session, token: str, purpose: Literal["reset", "verify"],
                 password: str | None = None) -> None:
    now = int(time.time())
    # Claim the link and mutate the user in one transaction; retries cannot reuse it.
    saved = db.scalar(update(AccountToken).where(
        AccountToken.token_hash == hash_token(token), AccountToken.purpose == purpose,
        AccountToken.consumed_at.is_(None), AccountToken.expires_at > now,
    ).values(consumed_at=now).returning(AccountToken))
    if saved is None:
        db.rollback()
        raise InvalidAccountLink()
    user = db.get(User, saved.user_id)
    if user is None or hash_token(user.email) != saved.email_hash:
        db.rollback()
        raise InvalidAccountLink()
    statement = update(User).where(
        User.id == saved.user_id, User.email == user.email,
        User.credential_version == saved.credential_version,
    )
    if purpose == "reset":
        # Legacy accounts without credentials still require operator recovery.
        if password is None or user.password_hash is None:
            db.rollback()
            raise InvalidAccountLink()
        statement = statement.values(password_hash=hash_password(password),
                                     credential_version=User.credential_version + 1)
    else:
        statement = statement.where(User.email_verified.is_(False)).values(email_verified=True)
    if db.scalar(statement.returning(User.id)) is None:
        db.rollback()
        raise InvalidAccountLink()
    if purpose == "reset":
        db.execute(delete(AuthSession).where(AuthSession.user_id == saved.user_id))
    db.commit()
