import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class AccountToken(Base):
    __tablename__ = "account_tokens"
    __table_args__ = (
        CheckConstraint("purpose IN ('reset','verify')", name="ck_account_tokens_purpose"),
    )
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(6), nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_version: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    consumed_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
