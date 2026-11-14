from collections.abc import Generator

import redis

from app.core.config import settings

_pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    socket_connect_timeout=2,
    socket_timeout=2,
    decode_responses=True,
)


def get_redis() -> Generator[redis.Redis, None, None]:
    client = redis.Redis(connection_pool=_pool)
    try:
        yield client
    finally:
        client.close()
