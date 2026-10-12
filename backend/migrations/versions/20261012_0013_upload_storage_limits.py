"""Account for existing stored note text and serialize storage admission."""

import sqlalchemy as sa
from alembic import op

revision = "20261012_0013"
down_revision = "20261012_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("storage_bytes", sa.BigInteger(), nullable=False,
                                        server_default=sa.text("0")))
    documents = sa.table("documents", sa.column("id"), sa.column("storage_bytes"))
    chunks = sa.table("document_chunks", sa.column("document_id"), sa.column("text"))
    # Count UTF-8 bytes, including the overlap stored in individual chunks.
    byte_length = (sa.func.octet_length(chunks.c.text)
                   if op.get_bind().dialect.name == "postgresql"
                   else sa.func.length(sa.cast(chunks.c.text, sa.LargeBinary)))
    amount = sa.select(sa.func.coalesce(sa.func.sum(byte_length), 0)).where(
        chunks.c.document_id == documents.c.id).scalar_subquery()
    op.execute(documents.update().values(storage_bytes=amount))
    op.create_table("storage_lock", sa.Column("id", sa.Integer(), autoincrement=False,
                                             primary_key=True),
                    sa.CheckConstraint("id = 1", name="ck_storage_lock_singleton"))
    op.execute(sa.text("INSERT INTO storage_lock (id) VALUES (1)"))


def downgrade() -> None:
    op.drop_table("storage_lock")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("storage_bytes")
