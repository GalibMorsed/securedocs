from urllib.parse import urlsplit, urlunsplit

from celery import Celery

from app.core.config import settings


def _default_broker_url(redis_url: str) -> str:
    parsed = urlsplit(redis_url)
    return urlunsplit(parsed._replace(path="/1"))


celery_app = Celery(
    "securedocs",
    broker=settings.celery_broker_url or _default_broker_url(settings.redis_url),
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    task_default_queue="document-processing",
    task_routes={"app.workers.tasks.process_document_task": {"queue": "document-processing"}},
    worker_prefetch_multiplier=1,
)
