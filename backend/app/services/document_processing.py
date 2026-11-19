from datetime import datetime, timedelta, timezone
import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentVersion
from app.services.document_chunking import chunk_pages
from app.services.document_extraction import (
    DocumentExtractionError,
    extract_document_text,
)
from app.storage import FileStorage, StorageError, StorageNotFound
from app.core.config import settings
from app.rag.embeddings import EmbeddingProvider, EmbeddingError, TransientEmbeddingError
from app.rag.budget import reserve_embedding_tokens
import redis

logger = logging.getLogger(__name__)
OCR_REQUIRED_MESSAGE = "No searchable text was found after OCR. Check the scan quality and configured OCR language, then retry."
STALE_PROCESSING_AFTER = timedelta(minutes=15)


def process_document(db: Session, document_id: UUID, storage: FileStorage, provider: EmbeddingProvider | object, budget_client: redis.Redis) -> str:
    document = db.scalar(
        select(Document)
        .where(Document.id == document_id)
        .with_for_update()
    )
    if document is None:
        return "missing"

    if document.status == "processing" and not is_processing_stale(document):
        return "processing"

    version = db.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )
    if document.status == "ready" and version is not None:
        pending = db.scalar(select(DocumentChunk.id).where(DocumentChunk.version_id == version.id, DocumentChunk.embedding.is_(None)).limit(1))
        if pending is None:
            return "ready"

    if version is None or not (version.storage_key or document.storage_key):
        _mark_failed(db, document, "This document does not have an uploaded file to process.")
        return "failed"

    document.status = "processing"
    document.processing_started_at = datetime.now(timezone.utc)
    document.processed_at = None
    document.processing_error = None
    db.commit()

    storage_key = version.storage_key or document.storage_key
    existing_chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.version_id == version.id).order_by(DocumentChunk.chunk_index)))
    try:
        if existing_chunks:
            chunks = None
        else:
            chunks = _extract_chunks(storage, storage_key, version.mime_type or document.mime_type)
    except DocumentExtractionError as exc:
        _mark_failed(db, document, str(exc))
        return "failed"
    except StorageNotFound:
        logger.warning("Document file unavailable during processing: %s", document_id)
        _mark_failed(db, document, "The uploaded file is unavailable in private storage.")
        return "failed"
    except StorageError:
        raise

    if chunks is not None:
        try:
            db.execute(delete(DocumentChunk).where(DocumentChunk.version_id == version.id))
            existing_chunks = [DocumentChunk(document_id=document.id, version_id=version.id, chunk_index=chunk.chunk_index, content=chunk.content, page_number=chunk.page_number, char_start=chunk.char_start, char_end=chunk.char_end, token_count=chunk.token_count) for chunk in chunks]
            db.add_all(existing_chunks)
            db.commit()
        except Exception:
            db.rollback()
            raise

    if not existing_chunks:
        _mark_failed(db, document, "No searchable text was found in this document.")
        return "failed"
    try:
        if callable(provider):
            provider = provider()
        total_tokens = sum(chunk.token_count for chunk in existing_chunks if chunk.embedding is None or chunk.embedding_model != settings.embedding_model)
        if total_tokens > settings.embedding_max_document_tokens:
            raise EmbeddingError("This document exceeds the configured embedding token limit.")
        pending_chunks = [chunk for chunk in existing_chunks if chunk.embedding is None or chunk.embedding_model != settings.embedding_model]
        for offset in range(0, len(pending_chunks), settings.embedding_batch_size):
            batch = pending_chunks[offset:offset + settings.embedding_batch_size]
            reserve_embedding_tokens(budget_client, sum(chunk.token_count for chunk in batch))
            vectors = provider.embed_batch([chunk.content for chunk in batch])
            if len(vectors) != len(batch):
                raise EmbeddingError("Embedding provider returned an incomplete response.")
            for chunk, vector in zip(batch, vectors, strict=True):
                chunk.embedding = vector
                chunk.embedding_model = settings.embedding_model
                chunk.embedded_at = datetime.now(timezone.utc)
                chunk.embedding_error = None
            db.commit()
        document.status = "ready"
        document.processing_error = None
        document.processed_at = datetime.now(timezone.utc)
        db.commit()
    except TransientEmbeddingError as exc:
        db.rollback()
        document = db.get(Document, document_id)
        if document:
            for chunk in db.scalars(select(DocumentChunk).where(DocumentChunk.version_id == version.id, (DocumentChunk.embedding.is_(None)) | (DocumentChunk.embedding_model != settings.embedding_model))):
                chunk.embedding_error = str(exc)[:1000]
            db.commit()
        raise
    except EmbeddingError as exc:
        db.rollback()
        document = db.get(Document, document_id)
        if document:
            document.status = "failed"
            document.processing_error = str(exc)[:1000]
            document.processed_at = datetime.now(timezone.utc)
            for chunk in db.scalars(select(DocumentChunk).where(DocumentChunk.version_id == version.id, (DocumentChunk.embedding.is_(None)) | (DocumentChunk.embedding_model != settings.embedding_model))):
                chunk.embedding_error = str(exc)[:1000]
            db.commit()
        return "failed"
    except Exception:
        db.rollback()
        raise
    return "ready"


def _extract_chunks(storage: FileStorage, storage_key: str, mime_type: str | None):
    try:
        stored = storage.open(storage_key)
        try:
            content = stored.stream.read()
        finally:
            stored.stream.close()
        pages = extract_document_text(content, mime_type or "")
        if not any(page.text.strip() for page in pages):
            message = (
                OCR_REQUIRED_MESSAGE
                if (mime_type or "") == "application/pdf"
                else "No searchable text was found in this document."
            )
            raise DocumentExtractionError(message)
        chunks = chunk_pages(pages)
        if not chunks:
            raise DocumentExtractionError("No searchable text was found in this document.")
    except (DocumentExtractionError, StorageNotFound, StorageError):
        raise
    except Exception as exc:
        raise DocumentExtractionError("The document text could not be extracted.") from exc
    return chunks


def mark_processing_retry_pending(db: Session, document_id: UUID) -> None:
    document = db.get(Document, document_id)
    if document is None:
        return
    document.status = "uploaded"
    document.processing_started_at = None
    document.processed_at = None
    document.processing_error = None
    db.commit()


def mark_processing_failed(db: Session, document_id: UUID, message: str) -> None:
    document = db.get(Document, document_id)
    if document is None:
        return
    _mark_failed(db, document, message)


def mark_queue_failed(db: Session, document: Document) -> None:
    document.status = "failed"
    document.processing_error = "Processing could not be queued. Please retry processing."
    document.processing_started_at = None
    document.processed_at = None
    db.commit()


def reset_for_retry(db: Session, document: Document) -> None:
    document.status = "uploaded"
    document.processing_started_at = None
    document.processed_at = None
    document.processing_error = None
    db.commit()


def is_processing_stale(document: Document) -> bool:
    started = document.processing_started_at
    if started is None:
        return True
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - started > STALE_PROCESSING_AFTER


def _mark_failed(db: Session, document: Document, message: str) -> None:
    document.status = "failed"
    document.processing_error = message[:1000]
    document.processed_at = datetime.now(timezone.utc)
    db.commit()
