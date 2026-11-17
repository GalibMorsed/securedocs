"""add processing state and versioned text chunks

Revision ID: 20261118_01
Revises: 91358817939d
Create Date: 2026-11-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261118_01"
down_revision: Union[str, None] = "91358817939d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("documents", sa.Column("processing_error", sa.Text(), nullable=True))
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index"),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name="ck_document_chunks_page_number",
        ),
        sa.CheckConstraint(
            "char_start >= 0 AND char_end > char_start",
            name="ck_document_chunks_character_range",
        ),
        sa.CheckConstraint("token_count >= 0", name="ck_document_chunks_token_count"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_id", "chunk_index", name="uq_document_chunk_version_index"
        ),
    )
    op.create_index(
        "ix_document_chunks_document_id", "document_chunks", ["document_id"]
    )
    op.create_index("ix_document_chunks_version_id", "document_chunks", ["version_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_version_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_column("documents", "processing_error")
    op.drop_column("documents", "processed_at")
    op.drop_column("documents", "processing_started_at")
