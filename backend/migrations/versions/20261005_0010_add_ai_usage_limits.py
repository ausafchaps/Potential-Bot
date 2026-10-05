"""Add shared AI generation budgets."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0010"
down_revision: str | None = "20261005_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_buckets",
        sa.Column("bucket_key", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("attempts >= 1", name=op.f("ck_ai_usage_buckets_positive_attempts")),
        sa.PrimaryKeyConstraint("bucket_key"),
    )
    op.create_index("ix_ai_usage_buckets_expires_at", "ai_usage_buckets", ["expires_at"])


def downgrade() -> None:
    op.drop_table("ai_usage_buckets")
