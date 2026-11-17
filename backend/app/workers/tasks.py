import logging
from uuid import UUID

from app.core.database import SessionLocal
from app.services.document_processing import (
    mark_processing_failed,
    mark_processing_retry_pending,
    process_document,
)
from app.storage import get_storage
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_document_task",
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_document_task(self, document_id: str) -> str:
    parsed_id = UUID(document_id)
    try:
        with SessionLocal() as db:
            return process_document(db, parsed_id, get_storage())
    except Exception as exc:
        logger.exception("Document processing attempt failed for %s", parsed_id)
        if self.request.retries < self.max_retries:
            with SessionLocal() as db:
                mark_processing_retry_pending(db, parsed_id)
            raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))

        try:
            with SessionLocal() as db:
                mark_processing_failed(
                    db,
                    parsed_id,
                    "Processing could not be completed after several attempts. Please retry processing.",
                )
        except Exception:
            logger.exception("Could not record final processing failure for %s", parsed_id)
        return "failed"
