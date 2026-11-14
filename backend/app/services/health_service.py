import time
from collections.abc import Callable

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.health import ServiceStatus


def _timed(name: str, fn: Callable[[], str]) -> ServiceStatus:
    """Run a check, capturing latency and turning any exception into a failed status."""
    start = time.perf_counter()
    try:
        detail = fn()
        ok = True
    except Exception as exc:  # noqa: BLE001 - health checks must never raise
        message = str(exc).strip().splitlines()
        detail = f"{type(exc).__name__}: {message[0] if message else 'unavailable'}"
        ok = False
    latency = round((time.perf_counter() - start) * 1000, 1)
    return ServiceStatus(name=name, ok=ok, detail=detail, latency_ms=latency)


def check_database(db: Session) -> ServiceStatus:
    def run() -> str:
        version = db.execute(text("SELECT version()")).scalar_one()
        return " ".join(str(version).split()[:2])

    return _timed("PostgreSQL", run)


def check_pgvector(db: Session) -> ServiceStatus:
    def run() -> str:
        version = db.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()
        if version is None:
            raise RuntimeError("extension not enabled - run `alembic upgrade head`")
        return f"pgvector {version}"

    return _timed("pgvector", run)


def check_redis(client: redis.Redis) -> ServiceStatus:
    def run() -> str:
        client.ping()
        info = client.info("server")
        return f"Redis {info.get('redis_version', 'unknown')}"

    return _timed("Redis", run)
