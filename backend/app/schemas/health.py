from typing import Literal

from pydantic import BaseModel


class ServiceStatus(BaseModel):
    name: str
    ok: bool
    detail: str
    latency_ms: float | None = None


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    app: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    environment: str
    services: list[ServiceStatus]
