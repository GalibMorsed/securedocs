import os
import tempfile
from pathlib import Path

from app.storage.base import (
    StorageError,
    StorageNotFound,
    StoredFile,
    validate_storage_key,
)


class LocalStorage:
    """Private filesystem storage; files are never mounted by the web server."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            self.root.chmod(0o700)

    def _path_for(self, key: str) -> Path:
        validate_storage_key(key)
        path = self.root / key
        if path.parent != self.root or path.parent.resolve() != self.root:
            raise StorageError("Storage key escaped the private storage directory")
        return path

    def store(self, key: str, content: bytes, content_type: str) -> None:
        destination = self._path_for(key)
        temp_path: Path | None = None
        try:
            descriptor, temp_name = tempfile.mkstemp(prefix=".upload-", dir=self.root)
            temp_path = Path(temp_name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if os.name != "nt":
                temp_path.chmod(0o600)
            os.replace(temp_path, destination)
        except OSError as exc:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise StorageError("Could not store the uploaded file") from exc

    def open(self, key: str) -> StoredFile:
        path = self._path_for(key)
        if path.is_symlink():
            raise StorageError("Storage object must not be a symbolic link")
        try:
            return StoredFile(stream=path.open("rb"))
        except FileNotFoundError as exc:
            raise StorageNotFound("Stored file was not found") from exc
        except OSError as exc:
            raise StorageError("Could not read the stored file") from exc

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("Could not delete the stored file") from exc
