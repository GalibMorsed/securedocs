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

logger = logging.getLogger(__name__)
OCR_REQUIRED_MESSAGE = (
    "No selectable text was found. This may be a scanned PDF; OCR is not enabled yet."
)
STALE_PROCESSING_AFTER = timedelta(minutes=15)


def process_document(db: Session, document_id: UUID, storage: FileStorage) -> str:
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
        has_chunks = db.scalar(
            select(DocumentChunk.id)
            .where(DocumentChunk.version_id == version.id)
            .limit(1)
        )
        if has_chunks is not None:
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
    try:
        stored = storage.open(storage_key)
        try:
            content = stored.stream.read()
        finally:
            stored.stream.close()
        pages = extract_document_text(content, version.mime_type or document.mime_type)
        if not any(page.text.strip() for page in pages):
            message = (
                OCR_REQUIRED_MESSAGE
                if (version.mime_type or document.mime_type) == "application/pdf"
                else "No searchable text was found in this document."
            )
            raise DocumentExtractionError(message)
        chunks = chunk_pages(pages)
        if not chunks:
            raise DocumentExtractionError("No searchable text was found in this document.")
    except DocumentExtractionError as exc:
        _mark_failed(db, document, str(exc))
        return "failed"
    except StorageNotFound:
        logger.warning("Document file unavailable during processing: %s", document_id)
        _mark_failed(db, document, "The uploaded file is unavailable in private storage.")
        return "failed"
    except StorageError:
        raise

    try:
        db.execute(
            delete(DocumentChunk).where(DocumentChunk.version_id == version.id)
        )
        db.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    version_id=version.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    token_count=chunk.token_count,
                )
                for chunk in chunks
            ]
        )
        document.status = "ready"
        document.processing_error = None
        document.processed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return "ready"


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
