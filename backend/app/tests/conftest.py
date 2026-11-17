import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app import models  # noqa: F401
from app.core.database import get_db
from app.core.database import Base
from app.core.redis import get_redis
from app.main import app
from app.storage import LocalStorage, get_storage
from app.workers.queue import get_processing_queue


@pytest.fixture
def client():
    # Dependencies are stubbed so unit tests never need real Postgres/Redis.
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_redis] = lambda: object()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(tmp_path):
    # Auth tests use an isolated in-memory database, never the developer database.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app.state.test_session = test_session
    test_storage = LocalStorage(tmp_path / "private-files")
    queued_document_ids = []
    app.state.test_storage = test_storage
    app.state.test_queued_document_ids = queued_document_ids

    def override_get_db():
        with test_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: test_storage
    app.dependency_overrides[get_processing_queue] = lambda: queued_document_ids.append
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_processing_queue, None)
        del app.state.test_session
        del app.state.test_storage
        del app.state.test_queued_document_ids
        engine.dispose()
