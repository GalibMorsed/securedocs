from functools import lru_cache

from app.core.config import settings
from app.storage.base import FileStorage
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


@lru_cache
def get_storage() -> FileStorage:
    if settings.storage_backend == "s3":
        return S3Storage()
    return LocalStorage(settings.local_storage_path)
