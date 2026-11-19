"""switch chunk embeddings to OpenRouter Qwen3 Embedding 8B

Revision ID: 20261119_03
Revises: 20261119_02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "20261119_03"
down_revision: Union[str, None] = "20261119_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Vectors from the previous provider are not compatible with Qwen's 4096 dimensions.
    op.drop_column("document_chunks", "embedding")
    op.add_column("document_chunks", sa.Column("embedding", Vector(4096), nullable=True))
    op.execute("""
        UPDATE document_chunks
        SET embedding_model = NULL,
            embedded_at = NULL,
            embedding_error = 'Re-embed this chunk with qwen/qwen3-embedding-8b.'
    """)
    op.execute("""
        UPDATE documents
        SET status = 'failed',
            processing_error = 'Embeddings were reset after changing providers. Retry processing to enable semantic search.',
            processed_at = NULL
        WHERE status = 'ready'
          AND EXISTS (SELECT 1 FROM document_chunks c WHERE c.document_id = documents.id)
    """)


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding")
    op.add_column("document_chunks", sa.Column("embedding", Vector(2048), nullable=True))
    op.execute("""
        UPDATE documents
        SET status = 'failed',
            processing_error = 'Embeddings must be regenerated after changing vector dimensions.',
            processed_at = NULL
        WHERE EXISTS (SELECT 1 FROM document_chunks c WHERE c.document_id = documents.id)
    """)
