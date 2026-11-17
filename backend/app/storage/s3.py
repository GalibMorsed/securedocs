from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.storage.base import (
    StorageError,
    StorageNotFound,
    StoredFile,
    validate_storage_key,
)


class S3Storage:
    """Private S3 storage using the standard AWS credential provider chain."""

    def __init__(self) -> None:
        if not settings.s3_bucket:
            raise StorageError("S3_BUCKET must be configured for S3 storage")
        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix.strip("/")
        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
        )

    def _object_key(self, key: str) -> str:
        validate_storage_key(key)
        return f"{self.prefix}/{key}" if self.prefix else key

    def store(self, key: str, content: bytes, content_type: str) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self._object_key(key),
                Body=content,
                ContentType=content_type,
                ServerSideEncryption=settings.s3_server_side_encryption,
            )
        except BotoCoreError as exc:
            raise StorageError("Could not store the uploaded file") from exc

    def open(self, key: str) -> StoredFile:
        try:
            response: dict[str, Any] = self.client.get_object(
                Bucket=self.bucket,
                Key=self._object_key(key),
            )
            return StoredFile(stream=response["Body"])
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"NoSuchKey", "404", "NotFound"}:
                raise StorageNotFound("Stored file was not found") from exc
            raise StorageError("Could not read the stored file") from exc
        except BotoCoreError as exc:
            raise StorageError("Could not read the stored file") from exc

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._object_key(key))
        except BotoCoreError as exc:
            raise StorageError("Could not delete the stored file") from exc
