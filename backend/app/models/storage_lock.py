from sqlalchemy import CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StorageLock(Base):
    """One transaction lock serializes shared storage admission and deletion."""
    __tablename__ = "storage_lock"
    __table_args__ = (CheckConstraint("id = 1", name="ck_storage_lock_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
