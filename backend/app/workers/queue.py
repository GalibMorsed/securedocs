from collections.abc import Callable
from uuid import UUID

from app.workers.tasks import process_document_task

EnqueueDocument = Callable[[UUID], None]


def enqueue_document_processing(document_id: UUID) -> None:
    process_document_task.delay(str(document_id))


def get_processing_queue() -> EnqueueDocument:
    return enqueue_document_processing
