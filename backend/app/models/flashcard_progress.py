import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class FlashcardProgress(Base):
    __tablename__ = "flashcard_progress"
    __table_args__ = (
        CheckConstraint("review_count >= 1", name="ck_flashcard_progress_reviews"),
        CheckConstraint("interval_minutes >= 1", name="ck_flashcard_progress_interval"),
        CheckConstraint("last_rating IN ('again','hard','good','easy')",
                        name="ck_flashcard_progress_rating"),
    )

    flashcard_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("flashcards.id", ondelete="CASCADE"), primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,
    )
    review_count: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    last_rating: Mapped[str] = mapped_column(String(5), nullable=False)
    last_reviewed_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    due_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
