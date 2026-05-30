"""create answer feedback

Revision ID: 20260530_0003
Revises: 20260525_0002
Create Date: 2026-05-30 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260530_0003"
down_revision: str | None = "20260525_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "answer_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("answer_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="rating_between_1_and_5"),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_answer_feedback_answer_id"),
        "answer_feedback",
        ["answer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_answer_feedback_answer_id"), table_name="answer_feedback")
    op.drop_table("answer_feedback")

