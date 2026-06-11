import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.flashcard import Flashcard


class FlashcardSetStatus(StrEnum):
    generated = "generated"
    insufficient_evidence = "insufficient_evidence"


class FlashcardDifficulty(StrEnum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class FlashcardSet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "flashcard_sets"

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(String(300), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    difficulty: Mapped[FlashcardDifficulty] = mapped_column(
        Enum(
            FlashcardDifficulty,
            name="flashcard_difficulty",
            values_callable=lambda difficulties: [
                difficulty.value for difficulty in difficulties
            ],
            create_constraint=True,
        ),
        nullable=False,
    )
    status: Mapped[FlashcardSetStatus] = mapped_column(
        Enum(
            FlashcardSetStatus,
            name="flashcard_set_status",
            values_callable=lambda statuses: [status.value for status in statuses],
            create_constraint=True,
        ),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    course: Mapped["Course"] = relationship(back_populates="flashcard_sets")
    cards: Mapped[list["Flashcard"]] = relationship(
        back_populates="flashcard_set",
        cascade="all, delete-orphan",
        order_by="Flashcard.position",
    )
