from io import BytesIO

import pytest
from botocore.exceptions import ClientError

from app.core.config import settings
from app.storage.base import StorageError, StorageNotFound
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


def test_local_storage_store_open_delete_and_reject_traversal(tmp_path):
    storage = LocalStorage(tmp_path / "private")
    key = "a" * 32 + ".txt"
    storage.store(key, b"private content", "text/plain")
    stored = storage.open(key)
    try:
        assert stored.stream.read() == b"private content"
    finally:
        stored.stream.close()
    storage.delete(key)
    with pytest.raises(StorageNotFound):
        storage.open(key)
    with pytest.raises(StorageError):
        storage.open("../secret.txt")


def test_s3_storage_uses_private_prefixed_object_and_maps_not_found(monkeypatch):
    calls = []

    class FakeS3:
        def put_object(self, **kwargs):
            calls.append(("put", kwargs))

        def get_object(self, **kwargs):
            calls.append(("get", kwargs))
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

        def delete_object(self, **kwargs):
            calls.append(("delete", kwargs))

    monkeypatch.setattr(settings, "s3_bucket", "private-test-bucket")
    monkeypatch.setattr(settings, "s3_prefix", "secure/files")
    monkeypatch.setattr("app.storage.s3.boto3.client", lambda *args, **kwargs: FakeS3())
    storage = S3Storage()
    key = "b" * 32 + ".pdf"
    storage.store(key, b"%PDF-1.7", "application/pdf")
    assert calls[0][1]["Bucket"] == "private-test-bucket"
    assert calls[0][1]["Key"] == f"secure/files/{key}"
    assert calls[0][1]["ServerSideEncryption"] in {"AES256", "aws:kms"}
    with pytest.raises(StorageNotFound):
        storage.open(key)
    storage.delete(key)
    assert calls[-1][1]["Key"] == f"secure/files/{key}"
