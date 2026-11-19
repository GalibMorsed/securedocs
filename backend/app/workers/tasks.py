import logging
from uuid import UUID
import redis

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.document_processing import (
    mark_processing_failed,
    mark_processing_retry_pending,
    process_document,
)
from app.storage import get_storage
from app.rag.embeddings import get_embedding_provider
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_document_task",
    max_retries=settings.embedding_max_retries,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_document_task(self, document_id: str) -> str:
    parsed_id = UUID(document_id)
    try:
        with SessionLocal() as db:
            client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            try:
                return process_document(db, parsed_id, get_storage(), get_embedding_provider, client)
            finally:
                client.close()
    except Exception as exc:
        logger.exception("Document processing attempt failed for %s", parsed_id)
        if self.request.retries < self.max_retries:
            with SessionLocal() as db:
                mark_processing_retry_pending(db, parsed_id)
            raise self.retry(exc=exc, countdown=settings.embedding_retry_backoff_seconds * (2 ** self.request.retries))

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
