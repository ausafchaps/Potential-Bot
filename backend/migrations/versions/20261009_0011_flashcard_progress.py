"""Persist per-student spaced repetition progress."""

import sqlalchemy as sa
from alembic import op

revision = "20261009_0011"
down_revision = "20261005_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flashcard_progress",
        sa.Column("flashcard_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("last_rating", sa.String(5), nullable=False),
        sa.Column("last_reviewed_at", sa.BigInteger(), nullable=False),
        sa.Column("due_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("flashcard_id", "user_id"),
        sa.ForeignKeyConstraint(["flashcard_id"], ["flashcards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("review_count >= 1", name="ck_flashcard_progress_reviews"),
        sa.CheckConstraint("interval_minutes >= 1", name="ck_flashcard_progress_interval"),
        sa.CheckConstraint("last_rating IN ('again','hard','good','easy')",
                           name="ck_flashcard_progress_rating"),
    )
    op.create_index("ix_flashcard_progress_due_at", "flashcard_progress", ["due_at"])


def downgrade() -> None:
    op.drop_index("ix_flashcard_progress_due_at", table_name="flashcard_progress")
    op.drop_table("flashcard_progress")
