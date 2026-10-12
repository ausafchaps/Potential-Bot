import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from pwdlib import PasswordHash
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AuthSession, User

password_hasher = PasswordHash.recommended()
# Equal-cost verification for unknown accounts and legacy accounts without credentials.
dummy_password_hash = password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    stored_hash = user.password_hash if user and user.password_hash else dummy_password_hash
    valid, upgraded_hash = password_hasher.verify_and_update(password, stored_hash)
    if not valid or user is None or user.password_hash is None:
        return None
    if upgraded_hash:
        if db.scalar(update(User).where(
            User.id == user.id, User.password_hash == stored_hash,
            User.credential_version == user.credential_version,
        ).values(password_hash=upgraded_hash).returning(User.id)) is None:
            db.rollback()
            return None
    return user


def create_session(db: Session, user: User) -> tuple[str, AuthSession]:
    # Serialize session creation with password resets. A login that verified an old
    # password before a concurrent reset cannot create a session after that reset.
    if db.scalar(update(User).where(
        User.id == user.id, User.credential_version == user.credential_version,
        User.password_hash == user.password_hash,
    ).values(credential_version=User.credential_version).returning(User.id)) is None:
        db.rollback()
        raise CredentialsChanged("Invalid email or password")
    token = secrets.token_urlsafe(32)
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(hours=settings.auth_session_hours),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return token, session


class CredentialsChanged(ValueError):
    pass
