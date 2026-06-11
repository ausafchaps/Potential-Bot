import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.flashcard_citation import FlashcardCitation
    from app.models.flashcard_set import FlashcardSet


class Flashcard(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "flashcards"
    __table_args__ = (
        UniqueConstraint(
            "flashcard_set_id",
            "position",
            name="uq_flashcards_set_position",
        ),
    )

    flashcard_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("flashcard_sets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)

    flashcard_set: Mapped["FlashcardSet"] = relationship(back_populates="cards")
    citations: Mapped[list["FlashcardCitation"]] = relationship(
        back_populates="flashcard",
        cascade="all, delete-orphan",
        order_by="FlashcardCitation.position",
    )
