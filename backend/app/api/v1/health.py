import redis
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.schemas.health import LivenessResponse, ReadinessResponse
from app.services import health_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    """Is the API process up? Does not touch any dependency."""
    return LivenessResponse(
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/services", response_model=ReadinessResponse)
def readiness(
    response: Response,
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> ReadinessResponse:
    """Can the API reach PostgreSQL, pgvector and Redis? Returns 503 if any check fails."""
    services = [
        health_service.check_database(db),
        health_service.check_pgvector(db),
        health_service.check_redis(redis_client),
    ]
    all_ok = all(s.ok for s in services)
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ok" if all_ok else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        services=services,
    )
