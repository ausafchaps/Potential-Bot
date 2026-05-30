import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.answer import Answer


class AnswerFeedback(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "answer_feedback"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="rating_between_1_and_5"),
    )

    answer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer: Mapped["Answer"] = relationship(back_populates="feedback_events")

