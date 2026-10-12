import uuid

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Course, Document, StorageLock
from app.schemas.storage import StorageAllowance, StorageUsage


class UploadLimited(Exception):
    def __init__(self, message: str, status_code: int = 413):
        super().__init__(message)
        self.status_code = status_code


class StorageUnavailable(Exception):
    pass


def lock_storage(db: Session) -> None:
    dialect = db.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise StorageUnavailable()
    insert = postgres_insert if dialect == "postgresql" else sqlite_insert
    # A no-op write holds the singleton row through quota checks and the commit.
    # SQLite takes its write lock here; PostgreSQL locks only this row.
    try:
        db.execute(insert(StorageLock).values(id=1).on_conflict_do_update(
            index_elements=[StorageLock.id], set_={"id": 1}))
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageUnavailable() from exc


def totals(db: Session, user_id: uuid.UUID | None = None) -> tuple[int, int]:
    statement = select(func.count(Document.id), func.coalesce(func.sum(Document.storage_bytes), 0))
    if user_id is not None:
        statement = statement.join(Course).where(Course.owner_id == user_id)
    row = db.execute(statement).one()
    return int(row[0]), int(row[1])


def check_capacity(db: Session, user_id: uuid.UUID, *, documents: int = 0,
                   text_bytes: int = 0) -> None:
    user_docs, user_bytes = totals(db, user_id)
    project_docs, project_bytes = totals(db)
    if (user_docs + documents > settings.storage_user_document_limit
            or user_bytes + text_bytes > settings.storage_user_text_bytes):
        db.rollback()
        raise UploadLimited("Your note storage is full. Delete documents from any of your courses "
                            "to free space, then try again.", 409)
    if (project_docs + documents > settings.storage_project_document_limit
            or project_bytes + text_bytes > settings.storage_project_text_bytes):
        db.rollback()
        raise UploadLimited("Shared note storage is full. Delete unused documents or contact "
                            "the app owner, then try again.", 409)


def check_file_size(raw_content: bytes) -> None:
    if len(raw_content) > settings.upload_max_bytes:
        raise UploadLimited(f"File exceeds the {settings.upload_max_bytes:,}-byte upload limit. "
                            "Choose a smaller file or split your notes.")


def check_text_size(character_count: int) -> None:
    if character_count > settings.upload_max_text_chars:
        raise UploadLimited(f"Document exceeds {settings.upload_max_text_chars:,} extracted "
                            "characters. Split it into smaller documents.")


def get_storage_usage(db: Session, user_id: uuid.UUID) -> StorageUsage:
    try:
        # Both aggregates use one statement so the snapshot is consistent.
        owned = select(Course.id).where(Course.owner_id == user_id)
        row = db.execute(select(
            func.count(Document.id), func.coalesce(func.sum(Document.storage_bytes), 0),
            func.coalesce(func.sum(case((Document.course_id.in_(owned), 1), else_=0)), 0),
            func.coalesce(func.sum(case((Document.course_id.in_(owned), Document.storage_bytes),
                                        else_=0)), 0),
        )).one()
        project_docs, project_bytes, user_docs, user_bytes = map(int, row)
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageUnavailable() from exc

    def allowance(used: int, limit: int) -> StorageAllowance:
        return StorageAllowance(used=used, limit=limit, remaining=max(0, limit - used))

    return StorageUsage(
        documents=allowance(user_docs, settings.storage_user_document_limit),
        text_bytes=allowance(user_bytes, settings.storage_user_text_bytes),
        max_file_bytes=settings.upload_max_bytes, max_pdf_pages=settings.upload_max_pdf_pages,
        max_text_chars=settings.upload_max_text_chars,
        shared_capacity_available=(project_docs < settings.storage_project_document_limit
                                   and project_bytes < settings.storage_project_text_bytes),
    )
