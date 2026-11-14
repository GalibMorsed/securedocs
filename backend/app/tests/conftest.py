import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.redis import get_redis
from app.main import app


@pytest.fixture
def client():
    # Dependencies are stubbed so unit tests never need real Postgres/Redis.
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_redis] = lambda: object()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
