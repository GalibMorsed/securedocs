from dataclasses import dataclass
import re
from typing import BinaryIO, Protocol


class StorageError(RuntimeError):
    """Base exception for private file storage failures."""


class StorageNotFound(StorageError):
    """Raised when a storage key has no corresponding object."""


_KEY_PATTERN = re.compile(r"\A[0-9a-f]{32}\.(?:pdf|txt|docx)\Z")


def validate_storage_key(key: str) -> str:
    if not _KEY_PATTERN.fullmatch(key):
        raise StorageError("Invalid storage key")
    return key


@dataclass
class StoredFile:
    stream: BinaryIO


class FileStorage(Protocol):
    def store(self, key: str, content: bytes, content_type: str) -> None: ...

    def open(self, key: str) -> StoredFile: ...

    def delete(self, key: str) -> None: ...
