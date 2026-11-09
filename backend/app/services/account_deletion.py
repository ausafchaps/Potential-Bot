from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import User
from app.services.auth import password_hasher
from app.services.storage import StorageUnavailable, lock_storage


class AccountDeletionDenied(ValueError):
    pass


def delete_own_account(db: Session, user: User, password: str) -> None:
    # Fresh reauthentication, with no password rehash/credential change during deletion.
    if (user.is_admin or not user.password_hash
            or not password_hasher.verify(password, user.password_hash)):
        raise AccountDeletionDenied("Account deletion could not be authorized")
    if db.get_bind().dialect.name == "sqlite":
        if db.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() != 1:
            raise StorageUnavailable()
    lock_storage(db)
    removed = db.scalar(delete(User).where(
        User.id == user.id, User.is_admin.is_(False),
        User.password_hash == user.password_hash,
        User.credential_version == user.credential_version,
    ).returning(User.id))
    if removed is None:
        db.rollback()
        raise AccountDeletionDenied("Account deletion could not be authorized")
    # FK cascades remove sessions, account links, courses, documents/chunks,
    # answers/citations, quizzes/attempts, and cards/progress in the same transaction.
    db.commit()
