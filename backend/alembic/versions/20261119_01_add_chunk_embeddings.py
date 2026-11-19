"""add pgvector embeddings to document chunks

Revision ID: 20261119_01
Revises: 20261118_01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "20261119_01"
down_revision: Union[str, None] = "20261118_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("embedding", Vector(1536), nullable=True))
    op.add_column("document_chunks", sa.Column("embedding_model", sa.String(length=100), nullable=True))
    op.add_column("document_chunks", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("document_chunks", sa.Column("embedding_error", sa.Text(), nullable=True))
    op.execute("""
        UPDATE documents
        SET status = 'failed',
            processing_error = 'Embeddings are pending. Retry processing to enable semantic search.'
        WHERE status = 'ready'
          AND storage_key IS NOT NULL
          AND EXISTS (SELECT 1 FROM document_chunks c WHERE c.document_id = documents.id)
    """)


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding_error")
    op.drop_column("document_chunks", "embedded_at")
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "embedding")
