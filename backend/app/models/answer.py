import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.citation import Citation
    from app.models.question import Question


class AnswerStatus(StrEnum):
    answered = "answered"
    insufficient_evidence = "insufficient_evidence"


class Answer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answers"

    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[AnswerStatus] = mapped_column(
        Enum(
            AnswerStatus,
            name="answer_status",
            values_callable=lambda statuses: [status.value for status in statuses],
            create_constraint=True,
        ),
        nullable=False,
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    question: Mapped["Question"] = relationship(back_populates="answers")
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="answer",
        cascade="all, delete-orphan",
        order_by="Citation.position",
    )

