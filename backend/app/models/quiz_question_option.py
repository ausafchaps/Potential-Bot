import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.quiz_question import QuizQuestion


class QuizQuestionOption(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "quiz_question_options"
    __table_args__ = (
        UniqueConstraint(
            "quiz_question_id",
            "position",
            name="uq_quiz_question_options_question_position",
        ),
    )

    quiz_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quiz_questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    question: Mapped["QuizQuestion"] = relationship(back_populates="options")

